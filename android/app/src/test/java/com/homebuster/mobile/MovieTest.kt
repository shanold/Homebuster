package com.homebuster.mobile

import org.junit.Assert.assertEquals
import org.junit.Test

class MovieTest {
    @Test fun posterUrlUsesTmdbImageHost() {
        val m = Movie(1,1,null,2,"Alien",1979,"","/abc.jpg",117,"Blu-ray",null,false)
        assertEquals("https://image.tmdb.org/t/p/w500/abc.jpg", m.posterUrl)
    }
}
