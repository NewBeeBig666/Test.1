package com.recsys.repo;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import com.recsys.entity.Book;

public interface BookRepository extends JpaRepository<Book, Long> {

    Page<Book> findByTitleContainingOrAuthorContainingIgnoreCase(
            String title, String author, Pageable pageable);

    @Query("select count(b) from Book b where b.imageUrl is null or b.imageUrl = ''")
    long countMissingCovers();
}
