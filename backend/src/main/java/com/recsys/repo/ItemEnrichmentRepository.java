package com.recsys.repo;

import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import com.recsys.entity.ItemEnrichment;

public interface ItemEnrichmentRepository extends JpaRepository<ItemEnrichment, Long> {

    Optional<ItemEnrichment> findByDomainAndItemId(String domain, Long itemId);

    Page<ItemEnrichment> findByDomainOrderByIdDesc(String domain, Pageable pageable);

    long countByDomain(String domain);
}
