package com.recsys;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 个性化推荐系统 - 业务后端入口。
 *
 * 架构：前端 -> SpringBoot(8080, 业务/缓存/行为) -> Python FastAPI(8001, 算法推理)
 * 存储：MySQL(业务数据) + Redis(推荐结果缓存)
 * 定时任务：外链有效性每日 04:30 抽查（EnrichmentService.scheduledCheck）
 */
@SpringBootApplication
@EnableScheduling
public class RecSysApplication {

    public static void main(String[] args) {
        SpringApplication.run(RecSysApplication.class, args);
    }
}
