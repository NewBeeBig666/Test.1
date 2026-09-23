package com.recsys.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import com.recsys.entity.User;
import com.recsys.repo.UserRepository;

/**
 * 用户认证：SHA-256(salt+password) 口令存储 + Redis 会话令牌（TTL 24h）。
 *
 * 令牌格式：Authorization: Bearer {uuid}
 * Redis：token:{uuid} -> "{userId}|{username}|{guest}"（Redis 不可用时降级本地内存）
 *
 * 体验用户（guest）：直接使用离线数据集的原始 User-ID（如图书域 BX 的 114、
 * 电影域 MovieLens 的 7），不注册即可以数据集真实用户身份体验个性化推荐。
 */
@Service
public class AuthService {

    public static final long GUEST_ID_LIMIT = 1_000_000_000L;
    /** 匿名游客 ID 空间起点（注册用户在 [1e9, 2e9)，匿名在 [2e9, 3e9)） */
    public static final long ANON_ID_BASE = 2_000_000_000L;
    private static final Duration TOKEN_TTL = Duration.ofHours(24);

    /** 会话信息（kind：user=注册 / guest=数据集体验用户 / anon=匿名游客） */
    public record Session(long userId, String username, boolean guest, String kind) {
        public String serialize() {
            return userId + "|" + username + "|" + guest + "|" + kind;
        }

        public static Session deserialize(String raw) {
            String[] p = raw.split("\\|", -1);
            if (p.length == 4) {
                try {
                    return new Session(Long.parseLong(p[0]), p[1],
                            Boolean.parseBoolean(p[2]), p[3]);
                } catch (NumberFormatException e) {
                    return null;
                }
            }
            // 兼容旧三段格式
            if (p.length == 3) {
                try {
                    boolean g = Boolean.parseBoolean(p[2]);
                    return new Session(Long.parseLong(p[0]), p[1], g, g ? "guest" : "user");
                } catch (NumberFormatException e) {
                    return null;
                }
            }
            return null;
        }
    }

    private final UserRepository repo;
    private final StringRedisTemplate redis;
    private final SecureRandom random = new SecureRandom();

    /** Redis 故障时的本地降级（60s 内不再重试 Redis） */
    private final Map<String, LocalEntry> local = new ConcurrentHashMap<>();
    private record LocalEntry(String value, long expireAtMs) {}
    private volatile long redisRetryAfterMs = 0;

    public AuthService(UserRepository repo, StringRedisTemplate redis) {
        this.repo = repo;
        this.redis = redis;
    }

    // ------------------------------------------------------------------
    // 注册 / 登录 / 体验用户
    // ------------------------------------------------------------------
    public Session register(String username, String password) {
        if (username == null || username.isBlank() || username.length() > 32) {
            throw new IllegalArgumentException("用户名须为 1~32 个字符");
        }
        if (password == null || password.length() < 6) {
            throw new IllegalArgumentException("密码至少 6 位");
        }
        if (repo.findByUsername(username).isPresent()) {
            throw new IllegalArgumentException("用户名已被占用");
        }
        String salt = newSalt();
        User user = new User(nextUserId(), username, sha256(salt + ":" + password), salt);
        repo.save(user);
        return new Session(user.getId(), user.getUsername(), false, "user");
    }

    public Session login(String username, String password) {
        User user = repo.findByUsername(username)
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));
        String expect = user.getPasswordHash();
        if (!expect.equals(sha256(user.getSalt() + ":" + password))) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        return new Session(user.getId(), user.getUsername(), false, "user");
    }

    /** 体验用户：使用离线数据集原始 User-ID（< 1e9） */
    public Session guest(long datasetUserId) {
        if (datasetUserId <= 0 || datasetUserId >= GUEST_ID_LIMIT) {
            throw new IllegalArgumentException("体验用户ID须为正整数且小于 " + GUEST_ID_LIMIT
                    + "（图书 1~278858 / 电影 1~610 / 课程 10000~12499）");
        }
        return new Session(datasetUserId, "体验用户-" + datasetUserId, true, "guest");
    }

    /**
     * 匿名游客：自动分配一次性会话，无需注册即可体验完整个性化流程。
     * ID 在 [2e9, 3e9) 空间（注册用户从 1e9 顺序分配、数据集用户 < 3e5，互不冲突），
     * 不落 sys_user 表，行为照常采集并可经算法侧 online_user_map 参与训练。
     */
    public Session autoGuest() {
        long id = ANON_ID_BASE + (long) (random.nextDouble() * 1_000_000_000L);
        return new Session(id, "游客", true, "anon");
    }

    // ------------------------------------------------------------------
    // 会话令牌
    // ------------------------------------------------------------------
    public String issueToken(Session session) {
        String token = UUID.randomUUID().toString().replace("-", "");
        String key = "token:" + token;
        if (tryRedis()) {
            try {
                redis.opsForValue().set(key, session.serialize(), TOKEN_TTL);
                return token;
            } catch (Exception e) {
                markRedisDown();
            }
        }
        local.put(key, new LocalEntry(session.serialize(),
                System.currentTimeMillis() + TOKEN_TTL.toMillis()));
        return token;
    }

    public Session resolve(String token) {
        if (token == null || token.isBlank()) {
            return null;
        }
        String key = "token:" + token;
        if (tryRedis()) {
            try {
                String raw = redis.opsForValue().get(key);
                return raw == null ? null : Session.deserialize(raw);
            } catch (Exception e) {
                markRedisDown();
            }
        }
        LocalEntry entry = local.get(key);
        if (entry == null) {
            return null;
        }
        if (System.currentTimeMillis() > entry.expireAtMs()) {
            local.remove(key);
            return null;
        }
        return Session.deserialize(entry.value());
    }

    public void revoke(String token) {
        if (token == null) {
            return;
        }
        String key = "token:" + token;
        if (tryRedis()) {
            try {
                redis.delete(key);
                return;
            } catch (Exception e) {
                markRedisDown();
            }
        }
        local.remove(key);
    }

    // ------------------------------------------------------------------
    // 工具
    // ------------------------------------------------------------------
    /** 注册用户ID从 1e9 起，避开离线数据集用户ID空间 */
    private long nextUserId() {
        Long maxId = repo.findMaxId();
        return Math.max(maxId == null ? 0 : maxId, GUEST_ID_LIMIT - 1) + 1;
    }

    private String newSalt() {
        byte[] bytes = new byte[16];
        random.nextBytes(bytes);
        return hex(bytes);
    }

    private String sha256(String text) {
        try {
            return hex(MessageDigest.getInstance("SHA-256")
                    .digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private String hex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16))
                    .append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    private boolean tryRedis() {
        return System.currentTimeMillis() >= redisRetryAfterMs;
    }

    private void markRedisDown() {
        redisRetryAfterMs = System.currentTimeMillis() + 60_000;
    }
}
