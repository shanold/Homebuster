package com.homebuster.mobile

import org.junit.Assert.assertEquals
import org.junit.Test

class MovieTest {
    @Test fun posterUrlUsesTmdbImageHost() {
        val m = Movie(
            id = 1,
            libraryId = 1,
            shelfId = null,
            tmdbId = 2,
            mediaType = "movie",
            title = "Alien",
            year = 1979,
            overview = "",
            posterPath = "/abc.jpg",
            runtime = 117,
            format = "Blu-ray",
            upc = null,
            watched = false
        )
        assertEquals("https://image.tmdb.org/t/p/w500/abc.jpg", m.posterUrl)
    }
}
