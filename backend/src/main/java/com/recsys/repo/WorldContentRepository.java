package com.recsys.repo;

import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import com.recsys.entity.WorldContent;

public interface WorldContentRepository extends JpaRepository<WorldContent, Long> {

    Page<WorldContent> findByDomainAndRegion(String domain, String region, Pageable pageable);

    /** 区域内标题搜索（精确限定搜索范围） */
    Page<WorldContent> findByDomainAndRegionAndTitleContainingIgnoreCase(String domain, String region, String title, Pageable pageable);

    Page<WorldContent> findByDomain(String domain, Pageable pageable);

    List<WorldContent> findByDomainOrderById(String domain);

    long countByDomain(String domain);

    long countByDomainAndRegion(String domain, String region);
}
