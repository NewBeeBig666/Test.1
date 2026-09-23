package com.recsys.controller;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;

import com.recsys.client.AlgoServiceClient;

/** 统一错误响应：算法服务不可达返回 502，参数问题返回 400 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler({AlgoServiceClient.AlgoServiceException.class, ResourceAccessException.class})
    public ResponseEntity<Map<String, Object>> algoDown(Exception e) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of("error", "推荐算法服务不可用，请确认 Python 服务已启动 (8001端口)",
                        "detail", String.valueOf(e.getMessage())));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> badRequest(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
    }
}
