package com.recsys.interceptor;

/** 当前请求的用户会话（由 AuthInterceptor 写入，请求结束后清理） */
public final class UserIdHolder {

    private static final ThreadLocal<AuthServiceSession> CTX = new ThreadLocal<>();

    public record AuthServiceSession(long userId, String username, boolean guest) {}

    private UserIdHolder() {
    }

    public static void set(long userId, String username, boolean guest) {
        CTX.set(new AuthServiceSession(userId, username, guest));
    }

    /** 获取当前登录用户ID；未登录抛出（拦截器已保证登录态，此为兜底） */
    public static long require() {
        AuthServiceSession s = CTX.get();
        if (s == null) {
            throw new IllegalStateException("未登录");
        }
        return s.userId();
    }

    public static AuthServiceSession get() {
        return CTX.get();
    }

    public static void clear() {
        CTX.remove();
    }
}
