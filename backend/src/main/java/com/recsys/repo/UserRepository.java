package com.recsys.repo;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import com.recsys.entity.User;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    /** 注册用户ID从 1e9 起分配（避免与离线数据集用户冲突） */
    @Query("select max(u.id) from User u")
    Long findMaxId();
}
