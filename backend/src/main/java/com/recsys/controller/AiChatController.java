package com.recsys.controller;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.recsys.interceptor.UserIdHolder;
import com.recsys.service.AiChatService;

/**
 * AI 客服/助手 Controller
 * <p>
 * 接收前端对话请求，调用 AiChatService 走智谱 GLM-4-Flash 模型，
 * 返回与推荐系统相关的解答。
 * <p>
 * 安全设计：
 * <ul>
 *   <li>历史消息的 role 被强制白名单过滤（仅允许 user/assistant），防止前端伪造 system 消息注入。</li>
 *   <li>对话内容仅在请求内存中短暂存在（转发给 LLM），后端不持久化任何用户对话。</li>
 *   <li>userId 从会话拦截器 ThreadLocal 中获取（UserIdHolder），不可被前端伪造。</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/ai")
public class AiChatController {

    private final AiChatService aiChatService;

    public AiChatController(AiChatService aiChatService) {
        this.aiChatService = aiChatService;
    }

    /**
     * 请求体结构：
     * {
     *   "question": "用户本次提问",
     *   "history": [ {"role": "user"|"assistant", "content": "..."} ]  // 最多保留 10 轮
     * }
     */
    public static class ChatRequest {
        public String question;
        public List<HistoryMessage> history;

        public static class HistoryMessage {
            public String role;
            public String content;
        }
    }

    /**
     * 响应体结构：{ "success": true, "answer": "AI 回答内容" }
     */
    @PostMapping("/chat")
    public Map<String, Object> chat(@RequestBody ChatRequest request) {
        long userId = UserIdHolder.require();

        String question = request.question == null ? "" : request.question.trim();
        if (question.isEmpty()) {
            return Map.of("success", false, "answer", "问题不能为空。");
        }
        if (question.length() > 2000) {
            return Map.of("success", false, "answer", "问题太长了，请精简后重试。");
        }

        // 历史消息过滤：role 白名单 + 内容截断，防止伪造 system 消息注入
        List<Map<String, String>> safeHistory = null;
        if (request.history != null && !request.history.isEmpty()) {
            safeHistory = request.history.stream()
                    .filter(m -> "user".equals(m.role) || "assistant".equals(m.role))
                    .limit(10)
                    .map(m -> {
                        String content = m.content == null ? "" : m.content;
                        if (content.length() > 500) content = content.substring(0, 500);
                        return Map.of("role", m.role, "content", content);
                    })
                    .toList();
        }

        try {
            String answer = aiChatService.chat(question, safeHistory, userId);
            return Map.of("success", true, "answer", answer);
        } catch (Exception e) {
            return Map.of("success", false, "answer", "AI 客服开小差了，请稍后再试～");
        }
    }
}
