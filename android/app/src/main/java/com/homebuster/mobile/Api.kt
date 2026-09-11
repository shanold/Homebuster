package com.homebuster.mobile

import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

data class LoginRequest(val username: String, val password: String, @SerializedName("device_name") val deviceName: String = "Homebuster Android")
data class User(val id: Int, val username: String, @SerializedName("is_admin") val isAdmin: Boolean)
data class LoginResponse(val token: String, val user: User)
data class ServerStatus(@SerializedName("server_version") val serverVersion: String, @SerializedName("api_version") val apiVersion: String, val status: String)
data class Movie(
    val id: Int, @SerializedName("library_id") val libraryId: Int, @SerializedName("shelf_id") val shelfId: Int?,
    @SerializedName("tmdb_id") val tmdbId: Int?, val title: String, val year: Int?, val overview: String,
    @SerializedName("poster_path") val posterPath: String?, val runtime: Int?, val format: String,
    val upc: String?, val watched: Boolean, val version: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null
) {
    val posterUrl: String? get() = posterPath?.let { "https://image.tmdb.org/t/p/w500$it" }
}
data class MoviesResponse(val movies: List<Movie>)
data class CollectionItem(val id: Int, @SerializedName("library_id") val libraryId: Int, val name: String, val description: String, @SerializedName("movie_count") val movieCount: Int)
data class CollectionsResponse(val collections: List<CollectionItem>)
data class Loan(val id: Int, @SerializedName("movie_id") val movieId: Int, val title: String, val borrower: String, @SerializedName("loaned_at") val loanedAt: String, @SerializedName("returned_at") val returnedAt: String?, val notes: String)
data class LoansResponse(val loans: List<Loan>)
data class TmdbResult(
    @SerializedName("tmdb_id") val tmdbId: Int, val title: String, val year: Int?, val overview: String,
    @SerializedName("poster_path") val posterPath: String?, @SerializedName("match_score") val matchScore: Int? = null
)
data class TmdbResponse(val results: List<TmdbResult>)
data class BarcodeProduct(@SerializedName("product_title") val productTitle: String?, @SerializedName("search_title") val searchTitle: String?)
data class BarcodeSearchAttempt(val title: String, val year: Int?, val results: Int, @SerializedName("best_score") val bestScore: Int)
data class BarcodeLookup(
    val title: String, @SerializedName("fallback_title") val fallbackTitle: String? = null, val year: Int?,
    val formats: List<String> = emptyList(), val format: String? = null, val edition: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null,
    val distributor: String? = null, val attempts: List<BarcodeSearchAttempt> = emptyList()
)
data class BarcodeResponse(
    val status: String,
    val upc: String?,
    val movie: Movie?,
    val product: BarcodeProduct?,
    val lookup: BarcodeLookup?,
    @SerializedName("best_match") val bestMatch: TmdbResult? = null,
    @SerializedName("tmdb_results") val tmdbResults: List<TmdbResult>? = null
)
data class AddMovieRequest(
    @SerializedName("tmdb_id") val tmdbId: Int?, val title: String, val year: Int?, val overview: String?,
    @SerializedName("poster_path") val posterPath: String?, val format: String, val upc: String?,
    val version: String? = null, val language: String? = null, val region: String? = null,
    @SerializedName("disc_count") val discCount: Int? = null
)

interface HomebusterApi {
    @GET("api/v1/status") suspend fun status(): ServerStatus
    @POST("api/v1/auth/login") suspend fun login(@Body body: LoginRequest): LoginResponse
    @GET("api/v1/movies") suspend fun movies(@Header("Authorization") auth: String, @Query("q") query: String? = null): MoviesResponse
    @GET("api/v1/movies/{id}") suspend fun movie(@Header("Authorization") auth: String, @Path("id") id: Int): Map<String, Movie>
    @GET("api/v1/collections") suspend fun collections(@Header("Authorization") auth: String): CollectionsResponse
    @GET("api/v1/collections/{id}/movies") suspend fun collectionMovies(@Header("Authorization") auth: String, @Path("id") id: Int): MoviesResponse
    @GET("api/v1/loans") suspend fun loans(@Header("Authorization") auth: String): LoansResponse
    @GET("api/v1/tmdb/search") suspend fun tmdb(@Header("Authorization") auth: String, @Query("q") query: String): TmdbResponse
    @GET("api/v1/barcodes/{upc}") suspend fun barcode(@Header("Authorization") auth: String, @Path("upc") upc: String): BarcodeResponse
    @POST("api/v1/movies") suspend fun addMovie(@Header("Authorization") auth: String, @Body body: AddMovieRequest): Map<String, Movie>
}

object ApiFactory {
    fun create(baseUrl: String): HomebusterApi {
        val normalized = if (baseUrl.endsWith('/')) baseUrl else "$baseUrl/"
        return Retrofit.Builder().baseUrl(normalized).client(OkHttpClient.Builder().build()).addConverterFactory(GsonConverterFactory.create()).build().create(HomebusterApi::class.java)
    }
}
