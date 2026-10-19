package com.recsys.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * AI 客服服务：调用智谱 GLM-4-Flash 模型解答推荐系统相关问题。
 * <p>
 * 核心机制：
 * <ul>
 *   <li><b>域内判定</b>：明显与推荐系统无关的问题（天气、股票等）直接短路拒答，不调用 API（防提示注入 + 节省调用）</li>
 *   <li><b>System Prompt 约束</b>：指定 AI 身份为"智荐系统客服小智"，仅回答系统功能、推荐算法、使用方法等</li>
 *   <li><b>用户偏好注入</b>：将当前用户的跨域兴趣标签注入 prompt，使回答与用户画像贴合</li>
 *   <li><b>多轮对话</b>：前端传入最近 10 轮对话作为上下文，历史在请求侧过滤不落库</li>
 * </ul>
 * 安全设计：API Key 存放在 backend/.env 中（不进代码仓库），通过环境变量注入。
 * 对话内容仅用于本次调用，服务端不持久化任何用户对话。
 */
@Service
public class AiChatService {

    /** System prompt：AI 身份与职责域约束 */
    private static final String SYSTEM_PROMPT = """
        你是"智荐"个性化推荐系统的 AI 客服助手，名字叫"小智"。

        你的职责范围（只回答以下相关问题）：
        1. 系统功能与使用：图书、课程、电影三个栏目的浏览、搜索、区域筛选、评分、收藏功能；详情抽屉的打开方式。
        2. 推荐功能解释：个性化推荐（ItemCF 协同过滤）、推荐指数（1-10 分制，基于全网公开数据综合评定）、探索模式（全球均衡展示）。
        3. 用户画像：三域兴趣画像的构成（基于用户的浏览、点击、评分、收藏行为），跨域推荐的意义。
        4. 算法原理：协同过滤、内容推荐、跨域推荐的基本概念，可以适度展开但不要过于学术化。

        回答规范：
        - 中文回答，口语化、友好、简洁，不超过 3 句话左右。
        - 对于与推荐系统无关的问题（闲聊、时事、其他领域的专业问题、写代码/写文章请求等），礼貌拒绝并引导用户回到系统相关话题。

        以下是当前用户的三域兴趣偏好画像（基于用户历史行为生成），在用户询问推荐内容时，请结合这些偏好进行个性化介绍：
        %s
        """;

    /** 明显无关的关键词：命中直接短路拒答（不调用 API，防提示注入） */
    private static final List<String> OFF_TOPIC_KEYWORDS = List.of(
        "天气", "股票", "基金", "汇率", "新闻", "体育", "彩票",
        "写作文", "写一篇", "帮我写", "论文怎么写", "游戏攻略",
        "炸鸡怎么做", "菜谱", "旅游攻略", "物理题", "数学题"
    );

    /** 域内关键词：包含则视为系统相关，允许通过 */
    private static final List<String> ON_TOPIC_KEYWORDS = List.of(
        "推荐", "图书", "书", "课程", "电影", "画像", "指数", "评分", "收藏", "系统",
        "平台", "算法", "协同过滤", "区域", "筛选", "搜索", "登录", "注册", "游客",
        "小智", "你好", "功能", "怎么", "如何", "是什么", "是什么意思", "help"
    );

    private static final String OFF_TOPIC_REPLY = "我是智荐系统的 AI 客服小智，只能解答推荐系统相关的功能与使用问题（如推荐功能、图书/课程/电影栏目、用户画像等），其他话题我帮不了您哦～";

    @Value("${ai.api-key:}")
    private String apiKey;

    @Value("${ai.base-url:https://open.bigmodel.cn/api/paas/v4/chat/completions}")
    private String baseUrl;

    @Value("${ai.model:glm-4-flash}")
    private String model;

    @Value("${ai.timeout-seconds:60}")
    private int timeoutSeconds;

    private final ObjectMapper mapper = new ObjectMapper();
    private final RecommendService recommendService;

    /** 域内判定结果 */
    public enum ChatVerdict { IN_DOMAIN, OFF_TOPIC }

    public AiChatService(RecommendService recommendService) {
        this.recommendService = recommendService;
        // 独立的 HTTP 客户端：长超时适配 LLM 生成
        this.httpClient = new RestTemplate();
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(timeoutSeconds * 1000);
        this.httpClient.setRequestFactory(factory);
    }

    private final RestTemplate httpClient;

    /**
     * AI 客服问答入口
     * @param question 用户当前问题
     * @param history 前端传入的最近对话历史（过滤为纯文本后作为上下文）
     * @param userId 当前登录用户 ID（用于偏好注入）
     * @return AI 回答（错误时返回降级提示，绝不抛异常）
     */
    public String chat(String question, List<Map<String, String>> history, long userId) {
        try {
            if (!isConfigured()) {
                return "AI 客服暂未配置 API Key，请联系管理员在 backend/.env 中配置。";
            }
            if (question == null || question.isBlank()) {
                return "请输入您的问题～";
            }

            // 域内判定：明显无关的话题直接短路拒答
            ChatVerdict verdict = judgeDomain(question);
            if (verdict == ChatVerdict.OFF_TOPIC) {
                return OFF_TOPIC_REPLY;
            }

            // 构建消息列表：system prompt + 对话历史 + 当前问题
            Map<String, Object> body = new HashMap<>();
            body.put("model", model);
            body.put("temperature", 0.6);
            body.put("max_tokens", 512);
            List<Map<String, String>> messages = new java.util.ArrayList<>();

            // System prompt（含用户偏好注入）
            messages.add(Map.of("role", "system", "content", buildSystemPrompt(userId)));

            // 历史对话（最多 10 轮，长度截断防滥用）
            if (history != null) {
                history.stream()
                    .filter(m -> {
                        String role = m.getOrDefault("role", "");
                        return "user".equals(role) || "assistant".equals(role);
                    })
                    .limit(10)
                    .forEach(m -> {
                        String content = m.getOrDefault("content", "");
                        if (content.length() > 500) content = content.substring(0, 500);
                        messages.add(Map.of("role", m.get("role"), "content", content));
                    });
            }

            // 当前问题（截断到 500 字符）
            String q = question.trim();
            if (q.length() > 500) q = q.substring(0, 500);
            messages.add(Map.of("role", "user", "content", q));

            body.put("messages", messages);

            // 调用智谱 API
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setBearerAuth(apiKey); // API Key 通过 Bearer Token 注入，不落日志

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);
            String response = httpClient.postForObject(baseUrl, entity, String.class);

            // 解析智谱 API 响应：choices[0].message.content
            JsonNode root = mapper.readTree(response);
            JsonNode choices = root.path("choices");
            if (!choices.isArray() || choices.isEmpty()) {
                return "抱歉，AI 客服暂时无法回答，请稍后再试。";
            }
            String answer = choices.get(0).path("message").path("content").asText("").trim();
            if (answer.isEmpty()) {
                return "抱歉，AI 客服暂时无法回答，请稍后再试。";
            }
            return answer;

        } catch (Exception e) {
            // 所有错误统一降级为友好提示，绝不让前端 500
            return "AI 客服暂时休息中，请稍后再试～";
        }
    }

    /** 是否已配置 API Key */
    public boolean isConfigured() {
        return apiKey != null && !apiKey.isBlank();
    }

    /**
     * 域内判定：不调用 API 的前置过滤。
     * 策略：包含 OFF_TOPIC 关键词且不包含 ON_TOPIC 关键词 → 直接拒答（节省 API 调用 + 防提示注入）。
     */
    private ChatVerdict judgeDomain(String question) {
        String q = question.toLowerCase();
        boolean hasOnTopic = ON_TOPIC_KEYWORDS.stream().anyMatch(q::contains);
        if (hasOnTopic) return ChatVerdict.IN_DOMAIN;

        boolean hasOffTopic = OFF_TOPIC_KEYWORDS.stream().anyMatch(q::contains);
        if (hasOffTopic) return ChatVerdict.OFF_TOPIC;

        // 未命中任何关键词的模糊问题：放行，交给 System Prompt 约束
        return ChatVerdict.IN_DOMAIN;
    }

    /**
     * 构建 System Prompt：固定职责域 + 当前用户的跨域兴趣标签注入。
     * 若用户画像获取失败或为空，注入通用描述。
     */
    private String buildSystemPrompt(long userId) {
        String profileDesc = "暂无历史行为数据（新用户），请推荐系统热门内容。";
        try {
            String profileJson = recommendService.globalProfile(userId);
            JsonNode interestTags = mapper.readTree(profileJson).path("interest_tags");
            if (interestTags.isArray() && !interestTags.isEmpty()) {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < Math.min(interestTags.size(), 5); i++) {
                    JsonNode tag = interestTags.get(i);
                    if (i > 0) sb.append("、");
                    sb.append(tag.path("tag").asText(""));
                }
                profileDesc = "用户偏好：" + sb;
            }
        } catch (Exception ignored) {
            // 画像获取失败不影响基本问答
        }
        return String.format(SYSTEM_PROMPT, profileDesc);
    }
}
