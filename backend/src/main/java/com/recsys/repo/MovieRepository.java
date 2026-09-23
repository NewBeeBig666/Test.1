package com.recsys.repo;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import com.recsys.entity.Movie;

public interface MovieRepository extends JpaRepository<Movie, Long> {

    Page<Movie> findByTitleContainingIgnoreCase(String title, Pageable pageable);

    Page<Movie> findByGenresContainingIgnoreCase(String genres, Pageable pageable);

    Page<Movie> findByTitleContainingIgnoreCaseAndGenresContainingIgnoreCase(
            String title, String genres, Pageable pageable);

    @Query("select count(m) from Movie m where m.posterUrl is null or m.posterUrl = ''")
    long countMissingCovers();
}
