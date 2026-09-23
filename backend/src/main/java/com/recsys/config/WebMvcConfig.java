package com.recsys.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import com.recsys.interceptor.AuthInterceptor;

/**
 * Web 配置：/api/** 鉴权拦截（/api/auth/** 放行）+ SPA 路由回退到 index.html
 * （Vue Router history 模式，前端构建产物由 SpringBoot 静态资源服务）
 * + /covers/** 本地生成封面（课程设计封面 PNG）资源映射。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final AuthInterceptor authInterceptor;

    @Value("${app.covers-dir:../data/covers}")
    private String coversDir;

    public WebMvcConfig(AuthInterceptor authInterceptor) {
        this.authInterceptor = authInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(authInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns("/api/auth/**", "/api/weread/**");
    }

    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        // 单段 SPA 路由（/books /profile 等）回退到入口页；含点的路径视为静态资源
        registry.addViewController("/{path:[^\\.]*}")
                .setViewName("forward:/index.html");
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // 课程设计封面（generate_course_covers.py 产出 data/covers/courses/*.png）
        // 用绝对路径 URI，避免相对 file: 位置在不同运行目录下解析失败
        java.io.File dir = new java.io.File(coversDir).getAbsoluteFile();
        registry.addResourceHandler("/covers/**")
                .addResourceLocations(dir.toURI().toString());
    }
}
