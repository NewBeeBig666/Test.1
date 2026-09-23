package com.recsys.repo;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import com.recsys.entity.Course;

public interface CourseRepository extends JpaRepository<Course, Long> {

    Page<Course> findByTitleContainingIgnoreCase(String title, Pageable pageable);

    Page<Course> findByCategoryIgnoreCase(String category, Pageable pageable);

    Page<Course> findByTitleContainingIgnoreCaseAndCategoryIgnoreCase(
            String title, String category, Pageable pageable);

    /** 中国课程（国内平台）：按平台排除 Udemy */
    Page<Course> findByPlatformNotIgnoreCase(String platform, Pageable pageable);
}
