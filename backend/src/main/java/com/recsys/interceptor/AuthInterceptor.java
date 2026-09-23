package com.recsys.interceptor;

import java.nio.charset.StandardCharsets;

import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import com.recsys.service.AuthService;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * API 鉴权拦截器：解析 Authorization: Bearer {token}，
 * /api/auth/** 与 OPTIONS 预检放行，其余 /api/** 需登录（注册用户或体验用户）。
 */
@Component
public class AuthInterceptor implements HandlerInterceptor {

    private final AuthService auth;

    public AuthInterceptor(AuthService auth) {
        this.auth = auth;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response,
                             Object handler) throws Exception {
        if (HttpMethod.OPTIONS.matches(request.getMethod())
                || request.getRequestURI().startsWith("/api/auth/")) {
            return true;
        }
        String header = request.getHeader("Authorization");
        String token = header != null && header.startsWith("Bearer ")
                ? header.substring(7) : null;
        AuthService.Session session = auth.resolve(token);
        if (session == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"error\":\"未登录或会话已过期\"}");
            return false;
        }
        // 管理接口：仅管理员账号可访问（毕设简化：用户名 admin；生产应使用角色权限模型）
        if (request.getRequestURI().startsWith("/api/admin/") && !"admin".equals(session.username())) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"error\":\"需要管理员权限（用户名 admin 登录）\"}");
            return false;
        }
        UserIdHolder.set(session.userId(), session.username(), session.guest());
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        UserIdHolder.clear();
    }
}
