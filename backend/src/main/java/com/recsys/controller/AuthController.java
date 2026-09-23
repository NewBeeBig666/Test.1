package com.recsys.controller;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.service.AuthService;

/**
 * 用户体系接口（免鉴权）：
 *   POST /api/auth/register    注册（ID 从 1e9 起，与离线数据集用户不冲突）
 *   POST /api/auth/login       登录 -> Bearer Token（Redis 会话，24h）
 *   POST /api/auth/guest       体验用户（离线数据集原始 User-ID）
 *   POST /api/auth/guest-auto  匿名游客（默认会话，无需注册即可体验个性化）
 *   POST /api/auth/logout      注销
 *   GET  /api/auth/me          当前会话
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService auth;

    public AuthController(AuthService auth) {
        this.auth = auth;
    }

    public record Credentials(String username, String password) {}

    public record GuestRequest(Long userId) {}

    private Map<String, Object> ok(AuthService.Session session) {
        return Map.of("token", auth.issueToken(session),
                "user", Map.of("id", session.userId(),
                        "username", session.username(),
                        "guest", session.guest(),
                        "kind", session.kind()));
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Credentials req) {
        if (req.username() == null || req.password() == null) {
            throw new IllegalArgumentException("username/password 不能为空");
        }
        return ok(auth.register(req.username().trim(), req.password()));
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Credentials req) {
        if (req.username() == null || req.password() == null) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        return ok(auth.login(req.username().trim(), req.password()));
    }

    @PostMapping("/guest")
    public Map<String, Object> guest(@RequestBody GuestRequest req) {
        if (req.userId() == null) {
            throw new IllegalArgumentException("userId 不能为空");
        }
        return ok(auth.guest(req.userId()));
    }

    /** 匿名游客：前端检测到无会话时自动调用，实现"免登录直达系统" */
    @PostMapping("/guest-auto")
    public Map<String, Object> guestAuto() {
        return ok(auth.autoGuest());
    }

    @PostMapping("/logout")
    public Map<String, Object> logout(
            @RequestHeader(value = "Authorization", required = false) String header) {
        if (header != null && header.startsWith("Bearer ")) {
            auth.revoke(header.substring(7));
        }
        return Map.of("status", "logged_out");
    }

    @GetMapping("/me")
    public Map<String, Object> me(
            @RequestHeader(value = "Authorization", required = false) String header) {
        String token = header != null && header.startsWith("Bearer ")
                ? header.substring(7) : null;
        AuthService.Session session = auth.resolve(token);
        if (session == null) {
            throw new IllegalArgumentException("未登录或会话已过期");
        }
        return Map.of("id", session.userId(),
                "username", session.username(),
                "guest", session.guest(),
                "kind", session.kind());
    }
}
