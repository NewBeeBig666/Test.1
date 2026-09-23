package com.recsys.config;

import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AppConfig {

    /** 调用算法服务的超时要短：推荐是同步链路，算法服务异常时快速失败 */
    @Bean
    public RestTemplate algoRestTemplate(RestTemplateBuilder builder) {
        return builder
                .setConnectTimeout(Duration.ofSeconds(2))
                .setReadTimeout(Duration.ofSeconds(10))
                .build();
    }

    @Bean
    public String algoBaseUrl(@Value("${algo.base-url}") String baseUrl) {
        return baseUrl;
    }
}
