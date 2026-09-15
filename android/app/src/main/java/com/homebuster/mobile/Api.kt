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
data class Library(
    val id: Int, val name: String, val role: String,
    @SerializedName("default_media_type") val defaultMediaType: String = "movie"
)
data class LibrariesResponse(val libraries: List<Library>)
data class Movie(
    val id: Int, @SerializedName("library_id") val libraryId: Int, @SerializedName("shelf_id") val shelfId: Int?,
    @SerializedName("tmdb_id") val tmdbId: Int?, @SerializedName("media_type") val mediaType: String = "movie", val title: String, val year: Int?, val overview: String,
    @SerializedName("poster_path") val posterPath: String?, val runtime: Int?, val format: String,
    val upc: String?, val watched: Boolean, val version: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null
) {
    val posterUrl: String? get() = posterPath?.let { if (it.startsWith("http://") || it.startsWith("https://")) it else "https://image.tmdb.org/t/p/w500$it" }
}
data class MoviesResponse(val movies: List<Movie>)
data class Shelf(val id: Int, @SerializedName("library_id") val libraryId: Int, val name: String, val description: String? = null)
data class ShelvesResponse(val shelves: List<Shelf>)
data class UpdateMovieRequest(val title: String? = null, val year: Int? = null, val format: String? = null, val version: String? = null, val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null, @SerializedName("shelf_id") val shelfId: Int? = null, val notes: String? = null)
data class LoanMovieRequest(val borrower: String, val phone: String? = null, val notes: String? = null)
data class CreateCollectionRequest(@SerializedName("library_id") val libraryId: Int, val name: String)
data class SimpleResponse(val ok: Boolean = true)
data class CollectionItem(val id: Int, @SerializedName("library_id") val libraryId: Int, val name: String, val description: String, @SerializedName("movie_count") val movieCount: Int)
data class CollectionsResponse(val collections: List<CollectionItem>)
data class Loan(val id: Int, @SerializedName("movie_id") val movieId: Int, val title: String, val borrower: String, @SerializedName("loaned_at") val loanedAt: String, @SerializedName("returned_at") val returnedAt: String?, val notes: String)
data class LoansResponse(val loans: List<Loan>)
data class CopyMetadata(
    val formats: List<String> = emptyList(), val format: String? = null, val edition: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null
)
data class TmdbResult(
    @SerializedName("tmdb_id") val tmdbId: Int, @SerializedName("media_type") val mediaType: String = "movie", val title: String, val year: Int?, val overview: String,
    @SerializedName("poster_path") val posterPath: String?, @SerializedName("match_score") val matchScore: Int? = null,
    @SerializedName("copy_metadata") val copyMetadata: CopyMetadata? = null
)
data class TmdbResponse(val results: List<TmdbResult>)
data class BarcodeProduct(@SerializedName("product_title") val productTitle: String?, @SerializedName("search_title") val searchTitle: String?)
data class BarcodeSearchAttempt(val title: String, val year: Int?, val results: Int, @SerializedName("best_score") val bestScore: Int)
data class BarcodeLookup(
    val title: String, @SerializedName("fallback_title") val fallbackTitle: String? = null, val year: Int?,
    val formats: List<String> = emptyList(), val format: String? = null, val edition: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null,
    val distributor: String? = null, val category: String? = null, val attempts: List<BarcodeSearchAttempt> = emptyList()
)
data class BoxSetSummary(val id: Int, val title: String, @SerializedName("library_id") val libraryId: Int? = null)
data class BarcodeResponse(
    val status: String,
    @SerializedName("media_type") val mediaType: String = "movie",
    val upc: String?,
    val movie: Movie?,
    @SerializedName("box_set") val boxSet: BoxSetSummary? = null,
    val product: BarcodeProduct?,
    val lookup: BarcodeLookup?,
    @SerializedName("best_match") val bestMatch: TmdbResult? = null,
    @SerializedName("tmdb_results") val tmdbResults: List<TmdbResult>? = null,
    @SerializedName("provider_status") val providerStatus: String? = null,
    val message: String? = null
)
data class AddMovieRequest(
    @SerializedName("library_id") val libraryId: Int?,
    @SerializedName("tmdb_id") val tmdbId: Int?, @SerializedName("media_type") val mediaType: String = "movie", val title: String, val year: Int?, val overview: String?,
    @SerializedName("poster_path") val posterPath: String?, val format: String, val upc: String?,
    val version: String? = null, val language: String? = null, val region: String? = null,
    @SerializedName("disc_count") val discCount: Int? = null
)

data class CollectionPart(
    val id: Int?, val title: String, @SerializedName("release_date") val releaseDate: String? = null,
    @SerializedName("poster_path") val posterPath: String? = null, val position: Int = 0
)
data class CollectionDetail(
    val id: Int, val title: String, val overview: String = "",
    @SerializedName("poster_path") val posterPath: String? = null, val parts: List<CollectionPart> = emptyList()
)
data class CollectionDetailResponse(val collection: CollectionDetail)
data class AddBoxSetMember(
    @SerializedName("tmdb_id") val tmdbId: Int?, val title: String, val year: Int?,
    @SerializedName("poster_path") val posterPath: String?, val position: Int
)
data class AddBoxSetRequest(
    @SerializedName("library_id") val libraryId: Int, val barcode: String?, val title: String,
    @SerializedName("tmdb_collection_id") val tmdbCollectionId: Int,
    @SerializedName("poster_path") val posterPath: String?, val format: String, val version: String? = null,
    val language: String? = null, val region: String? = null, @SerializedName("disc_count") val discCount: Int? = null,
    val status: String = "owned", val members: List<AddBoxSetMember>
)
data class BoxSetResponse(@SerializedName("box_set") val boxSet: BoxSetSummary)

interface HomebusterApi {
    @GET("api/v1/status") suspend fun status(): ServerStatus
    @POST("api/v1/auth/login") suspend fun login(@Body body: LoginRequest): LoginResponse
    @GET("api/v1/libraries") suspend fun libraries(@Header("Authorization") auth: String): LibrariesResponse
    @GET("api/v1/movies") suspend fun movies(@Header("Authorization") auth: String, @Query("q") query: String? = null, @Query("library_id") libraryId: Int? = null): MoviesResponse
    @GET("api/v1/movies/{id}") suspend fun movie(@Header("Authorization") auth: String, @Path("id") id: Int): Map<String, Movie>
    @PATCH("api/v1/movies/{id}") suspend fun updateMovie(@Header("Authorization") auth: String, @Path("id") id: Int, @Body body: UpdateMovieRequest): Map<String, Movie>
    @DELETE("api/v1/movies/{id}") suspend fun deleteMovie(@Header("Authorization") auth: String, @Path("id") id: Int): SimpleResponse
    @POST("api/v1/movies/{id}/loan") suspend fun loanMovie(@Header("Authorization") auth: String, @Path("id") id: Int, @Body body: LoanMovieRequest): SimpleResponse
    @POST("api/v1/movies/{id}/return") suspend fun returnMovie(@Header("Authorization") auth: String, @Path("id") id: Int): SimpleResponse
    @GET("api/v1/shelves") suspend fun shelves(@Header("Authorization") auth: String): ShelvesResponse
    @GET("api/v1/collections") suspend fun collections(@Header("Authorization") auth: String): CollectionsResponse
    @POST("api/v1/collections") suspend fun createCollection(@Header("Authorization") auth: String, @Body body: CreateCollectionRequest): Map<String, CollectionItem>
    @DELETE("api/v1/collections/{id}") suspend fun deleteCollection(@Header("Authorization") auth: String, @Path("id") id: Int): SimpleResponse
    @GET("api/v1/collections/{id}/movies") suspend fun collectionMovies(@Header("Authorization") auth: String, @Path("id") id: Int): MoviesResponse
    @GET("api/v1/loans") suspend fun loans(@Header("Authorization") auth: String): LoansResponse
    @GET("api/v1/tmdb/search") suspend fun tmdb(@Header("Authorization") auth: String, @Query("q") query: String, @Query("media_type") mediaType: String = "movie"): TmdbResponse
    @GET("api/v1/barcodes/{upc}") suspend fun barcode(@Header("Authorization") auth: String, @Path("upc") upc: String, @Query("media_type") mediaType: String = "movie", @Query("library_id") libraryId: Int? = null): BarcodeResponse
    @GET("api/v1/tmdb/collections/{id}") suspend fun collectionDetails(@Header("Authorization") auth: String, @Path("id") id: Int): CollectionDetailResponse
    @POST("api/v1/movies") suspend fun addMovie(@Header("Authorization") auth: String, @Body body: AddMovieRequest): Map<String, Movie>
    @POST("api/v1/box-sets") suspend fun addBoxSet(@Header("Authorization") auth: String, @Body body: AddBoxSetRequest): BoxSetResponse
}

object ApiFactory {
    fun create(baseUrl: String): HomebusterApi {
        val normalized = if (baseUrl.endsWith('/')) baseUrl else "$baseUrl/"
        return Retrofit.Builder().baseUrl(normalized).client(OkHttpClient.Builder().build()).addConverterFactory(GsonConverterFactory.create()).build().create(HomebusterApi::class.java)
    }
}
