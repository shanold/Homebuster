package com.homebuster.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import kotlinx.coroutines.launch
import retrofit2.HttpException

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { HomebusterTheme { HomebusterApp(SessionStore(this)) } }
    }
}

enum class Screen { LOGIN, LIBRARY, DETAILS, COLLECTIONS, LOANS, SCANNER, BARCODE_RESULT }

@Composable
fun HomebusterApp(store: SessionStore) {
    val context = LocalContext.current
    var localNetworkGranted by remember {
        mutableStateOf(Build.VERSION.SDK_INT < 37 || context.checkSelfPermission(Manifest.permission.ACCESS_LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED)
    }
    val localNetworkPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> localNetworkGranted = granted }
    var server by remember { mutableStateOf(store.serverUrl ?: "") }
    var token by remember { mutableStateOf(store.token) }
    var serverVersion by remember { mutableStateOf<String?>(null) }
    var screen by remember { mutableStateOf(if (token == null || server.isBlank()) Screen.LOGIN else Screen.LIBRARY) }
    var selected by remember { mutableStateOf<Movie?>(null) }
    var scanned by remember { mutableStateOf<BarcodeResponse?>(null) }
    val api = remember(server) { if (server.startsWith("http://") || server.startsWith("https://")) ApiFactory.create(server) else null }

    val navigateBack: () -> Unit = {
        screen = when (screen) {
            Screen.DETAILS, Screen.COLLECTIONS, Screen.LOANS, Screen.SCANNER, Screen.BARCODE_RESULT -> Screen.LIBRARY
            else -> screen
        }
    }
    BackHandler(enabled = screen != Screen.LOGIN && screen != Screen.LIBRARY) { navigateBack() }

    Surface(Modifier.fillMaxSize(), color = HbBackground) {
        when (screen) {
            Screen.LOGIN -> LoginScreen(server, { server = it }, localNetworkGranted, {
                if (Build.VERSION.SDK_INT >= 37) localNetworkPermissionLauncher.launch(Manifest.permission.ACCESS_LOCAL_NETWORK)
            }) { normalizedServer, newToken, detectedVersion ->
                store.serverUrl = normalizedServer
                store.token = newToken
                server = normalizedServer
                token = newToken
                serverVersion = detectedVersion
                screen = Screen.LIBRARY
            }
            Screen.LIBRARY -> LibraryScreen(api!!, token!!, serverVersion,
                onMovie = { selected = it; screen = Screen.DETAILS },
                onCollections = { screen = Screen.COLLECTIONS },
                onLoans = { screen = Screen.LOANS },
                onScan = { screen = Screen.SCANNER },
                onLogout = { store.clear(); token = null; serverVersion = null; screen = Screen.LOGIN })
            Screen.DETAILS -> MovieDetailScreen(selected!!, navigateBack)
            Screen.COLLECTIONS -> CollectionsScreen(api!!, token!!, navigateBack)
            Screen.LOANS -> LoansScreen(api!!, token!!, navigateBack)
            Screen.SCANNER -> ScannerScreen(onCode = { code ->
                scanned = BarcodeResponse("loading", code, null, null, null, null)
                screen = Screen.BARCODE_RESULT
            }, onBack = navigateBack)
            Screen.BARCODE_RESULT -> BarcodeResultScreen(api!!, token!!, scanned?.upc.orEmpty(), { scanned = it }, navigateBack)
        }
    }
}

private fun normalizeServerUrl(value: String): String {
    var normalized = value.trim()
    if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) normalized = "http://$normalized"
    if (!normalized.endsWith('/')) normalized += "/"
    return normalized
}

@Composable
private fun LoginScreen(
    server: String,
    onServer: (String) -> Unit,
    localNetworkGranted: Boolean,
    onRequestLocalNetwork: () -> Unit,
    onLoggedIn: (String, String, String) -> Unit
) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val horizontal = if (maxWidth > 560.dp) (maxWidth - 520.dp) / 2 else 20.dp
        Column(Modifier.fillMaxSize().padding(horizontal = horizontal), verticalArrangement = Arrangement.Center) {
            HomebusterPanel {
                Text("Homebuster", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.ExtraBold)
                Text("Your movie library, in your pocket.", color = HbMuted)
                Text("App v${BuildConfig.VERSION_NAME}", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                if (Build.VERSION.SDK_INT >= 37 && !localNetworkGranted) {
                    Spacer(Modifier.height(18.dp))
                    Card(colors = CardDefaults.cardColors(containerColor = HbPanel2), border = BorderStroke(1.dp, HbLine)) {
                        Column(Modifier.padding(14.dp)) {
                            Text("Local network access required", fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(4.dp))
                            Text("Android 17 requires permission before Homebuster can connect to a server on your home network.", color = HbMuted)
                            Spacer(Modifier.height(10.dp))
                            Button(onClick = onRequestLocalNetwork) { Text("Allow local network access") }
                        }
                    }
                }
                Spacer(Modifier.height(20.dp))
                OutlinedTextField(server, onServer, label = { Text("Homebuster server URL") }, placeholder = { Text("http://192.168.50.83:8092") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(username, { username = it }, label = { Text("Username") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
                error?.let { Spacer(Modifier.height(10.dp)); HomebusterErrorCard(it) }
                Spacer(Modifier.height(16.dp))
                Button(
                    enabled = !busy && localNetworkGranted && server.isNotBlank() && username.isNotBlank(),
                    onClick = {
                        busy = true; error = null
                        scope.launch {
                            try {
                                val current = normalizeServerUrl(server)
                                val loginApi = ApiFactory.create(current)
                                val status = loginApi.status()
                                val login = loginApi.login(LoginRequest(username, password))
                                onLoggedIn(current, login.token, status.serverVersion)
                            } catch (e: Exception) { error = friendlyLogin(e) } finally { busy = false }
                        }
                    }, modifier = Modifier.fillMaxWidth()
                ) { Text(if (busy) "Signing in…" else "Sign in") }
            }
        }
    }
}

private fun friendlyLogin(e: Exception): String = when (e) {
    is HttpException -> when (e.code()) {
        401 -> "Incorrect username or password."
        403 -> "This account is not allowed to sign in."
        else -> "Homebuster returned HTTP ${e.code()}."
    }
    else -> e.message ?: "Could not connect to Homebuster."
}

private fun friendly(e: Exception): String = when (e) {
    is HttpException -> when (e.code()) {
        401 -> "Your Homebuster session is no longer valid. Please sign in again."
        403 -> "You do not have permission to do that."
        404 -> "Homebuster could not find that item."
        else -> "Homebuster returned HTTP ${e.code()}."
    }
    else -> e.message ?: "Connection failed"
}

@Composable
private fun LibraryScreen(api: HomebusterApi, token: String, serverVersion: String?, onMovie: (Movie) -> Unit, onCollections: () -> Unit, onLoans: () -> Unit, onScan: () -> Unit, onLogout: () -> Unit) {
    var movies by remember { mutableStateOf<List<Movie>>(emptyList()) }
    var query by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(query) { try { movies = api.movies("Bearer $token", query.ifBlank { null }).movies; error = null } catch (e: Exception) { error = friendly(e) } }
    Column(Modifier.fillMaxSize()) {
        HomebusterTopBar("App v${BuildConfig.VERSION_NAME} • Server v${serverVersion ?: "unknown"}", "Log out", onLogout)
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            OutlinedTextField(query, { query = it }, label = { Text("Search my movies") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCollections, modifier = Modifier.weight(1f)) { Text("Collections") }
                OutlinedButton(onClick = onLoans, modifier = Modifier.weight(1f)) { Text("Loans") }
            }
            Spacer(Modifier.height(8.dp))
            Button(onClick = onScan, modifier = Modifier.fillMaxWidth()) { Text("Scan barcode") }
            error?.let { Spacer(Modifier.height(10.dp)); HomebusterErrorCard(it) }
        }
        if (movies.isEmpty() && error == null) {
            Box(Modifier.fillMaxSize().padding(horizontal = 16.dp)) { HomebusterEmptyState(if (query.isBlank()) "No movies in this library yet." else "No movies match your search.") }
        } else {
            LazyVerticalGrid(
                GridCells.Adaptive(155.dp), modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)
            ) { items(movies, key = { it.id }) { HomebusterMovieCard(it) { onMovie(it) } } }
        }
    }
}

@Composable
private fun MovieDetailScreen(movie: Movie, onBack: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { HomebusterScreenHeader("Movie details", onBack) }
        item {
            HomebusterPanel {
                AsyncImage(model = movie.posterUrl, contentDescription = movie.title, modifier = Modifier.fillMaxWidth().heightIn(max = 520.dp).aspectRatio(2f / 3f), contentScale = ContentScale.Fit)
                Spacer(Modifier.height(14.dp))
                Text(movie.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    movie.year?.let { HomebusterMetaChip(it.toString()) }
                    if (movie.format.isNotBlank()) HomebusterMetaChip(movie.format)
                    movie.runtime?.let { HomebusterMetaChip("$it min") }
                }
                movie.upc?.let { Spacer(Modifier.height(10.dp)); Text("UPC: $it", color = HbMuted, style = MaterialTheme.typography.bodySmall) }
            }
        }
        if (movie.overview.isNotBlank()) item { HomebusterPanel { Text("Overview", fontWeight = FontWeight.Bold); Spacer(Modifier.height(6.dp)); Text(movie.overview, color = HbMuted) } }
    }
}

@Composable
private fun CollectionsScreen(api: HomebusterApi, token: String, onBack: () -> Unit) {
    var data by remember { mutableStateOf<List<CollectionItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { runCatching { api.collections("Bearer $token").collections }.onSuccess { data = it }.onFailure { error = friendly(it as Exception) } }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { HomebusterScreenHeader("Collections", onBack) }
        error?.let { item { HomebusterErrorCard(it) } }
        if (data.isEmpty() && error == null) item { HomebusterEmptyState("No collections yet.") }
        items(data, key = { it.id }) { c -> HomebusterPanel { Text(c.name, fontWeight = FontWeight.Bold); Text("${c.movieCount} movies", color = HbMuted, style = MaterialTheme.typography.bodySmall) } }
    }
}

@Composable
private fun LoansScreen(api: HomebusterApi, token: String, onBack: () -> Unit) {
    var data by remember { mutableStateOf<List<Loan>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { runCatching { api.loans("Bearer $token").loans }.onSuccess { data = it }.onFailure { error = friendly(it as Exception) } }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { HomebusterScreenHeader("Loans", onBack) }
        error?.let { item { HomebusterErrorCard(it) } }
        if (data.isEmpty() && error == null) item { HomebusterEmptyState("No loan history yet.") }
        items(data, key = { it.id }) { loan ->
            HomebusterPanel {
                Text(loan.title, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                if (loan.returnedAt == null) Text("Loaned to ${loan.borrower}", color = HbWarning)
                else Text("Returned", color = HbGood)
                Text("Loaned ${loan.loanedAt}", color = HbMuted, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun BarcodeResultScreen(api: HomebusterApi, token: String, upc: String, onLoaded: (BarcodeResponse) -> Unit, onBack: () -> Unit) {
    var result by remember(upc) { mutableStateOf<BarcodeResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(upc) {
        try { result = api.barcode("Bearer $token", upc); onLoaded(result!!) }
        catch (e: HttpException) { error = if (e.code() == 404) "Barcode $upc is not in your library and the server could not identify it." else friendly(e) }
        catch (e: Exception) { error = friendly(e) }
    }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { HomebusterScreenHeader("Barcode lookup", onBack) }
        item { Text("UPC $upc", color = HbMuted, style = MaterialTheme.typography.bodySmall) }
        when (val r = result) {
            null -> item { if (error != null) HomebusterErrorCard(error!!) else HomebusterPanel { Text("Looking up barcode…", color = HbMuted) } }
            else -> if (r.status == "owned" && r.movie != null) {
                item { HomebusterPanel { Text("You already own this.", color = HbGood, fontWeight = FontWeight.Bold); Spacer(Modifier.height(4.dp)); Text(r.movie.title, style = MaterialTheme.typography.titleLarge); Text(r.movie.format, color = HbMuted) } }
            } else {
                item {
                    HomebusterPanel {
                        Text(r.product?.productTitle ?: "Product found", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        r.lookup?.let {
                            Spacer(Modifier.height(8.dp))
                            Text("Searching TMDb for:", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                            Text(it.title + (it.year?.let { y -> " ($y)" } ?: ""), color = HbAccent)
                        }
                        Spacer(Modifier.height(8.dp))
                        val count = r.tmdbResults?.size ?: 0
                        Text(if (count == 0) "No TMDb matches found" else "$count TMDb matches", color = if (count == 0) HbWarning else HbGood)
                    }
                }
                items(r.tmdbResults.orEmpty()) { match ->
                    HomebusterPanel {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            match.posterPath?.let { AsyncImage(model = "https://image.tmdb.org/t/p/w185$it", contentDescription = match.title, modifier = Modifier.width(74.dp).aspectRatio(2f / 3f), contentScale = ContentScale.Crop) }
                            Column { Text(match.title, fontWeight = FontWeight.Bold); match.year?.let { Text(it.toString(), color = HbMuted) }; if (match.overview.isNotBlank()) Text(match.overview, color = HbMuted, style = MaterialTheme.typography.bodySmall, maxLines = 4) }
                        }
                    }
                }
            }
        }
    }
}
