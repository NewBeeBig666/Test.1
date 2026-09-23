package com.recsys.repo;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.recsys.entity.BehaviorEvent;

public interface BehaviorEventRepository extends JpaRepository<BehaviorEvent, Long> {

    List<BehaviorEvent> findTop50ByUserIdOrderByCreatedAtDesc(Long userId);
}
