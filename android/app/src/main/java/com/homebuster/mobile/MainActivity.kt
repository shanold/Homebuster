package com.homebuster.mobile

// Navigation/state map:
// HomebusterApp owns connection/authentication state plus the currently selected library/item.
// Individual screens receive real server DTOs and callbacks rather than maintaining a second
// inventory database. detailsReturnScreen preserves the context a detail screen was opened from.

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
import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
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

enum class Screen { LOGIN, LIBRARY, DETAILS, COLLECTIONS, COLLECTION_DETAIL, LOANS, LOAN_FORM, MORE, SHELF_DETAIL, SCANNER, BARCODE_RESULT }

enum class ShelfViewMode { FRONT, SPINES }

data class MovieGroup(val key: String, val primary: Movie, val copies: List<Movie>) {
    val formatsSummary: String
        get() = copies.groupingBy { it.format.ifBlank { "Unknown" } }.eachCount().entries
            .sortedBy { it.key.lowercase() }
            .joinToString(" • ") { (format, count) -> if (count > 1) "$format ×$count" else format }
}

private fun normalizeGroupTitle(title: String): String =
    title.lowercase().replace(Regex("[^a-z0-9]+"), " ").trim()

private fun groupMovies(movies: List<Movie>): List<MovieGroup> {
    return movies.groupBy { movie ->
        movie.tmdbId?.let { "tmdb:${movie.mediaType}:$it" }
            ?: "manual:${movie.mediaType}:${normalizeGroupTitle(movie.title)}:${movie.year ?: ""}"
    }.map { (key, copies) ->
        val primary = copies.firstOrNull { it.posterUrl != null } ?: copies.first()
        MovieGroup(key, primary, copies.sortedWith(compareBy<Movie> { it.format.lowercase() }.thenBy { it.version ?: "" }))
    }.sortedBy { it.primary.title.lowercase() }
}

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
    var loginMessage by remember { mutableStateOf<String?>(null) }
    var screen by remember { mutableStateOf(if (token == null || server.isBlank()) Screen.LOGIN else Screen.LIBRARY) }
    var detailsReturnScreen by remember { mutableStateOf(Screen.LIBRARY) }
    var selected by remember { mutableStateOf<MovieGroup?>(null) }
    var selectedCopy by remember { mutableStateOf<Movie?>(null) }
    var selectedCollection by remember { mutableStateOf<CollectionItem?>(null) }
    var selectedShelf by remember { mutableStateOf<Shelf?>(null) }
    var scanned by remember { mutableStateOf<BarcodeResponse?>(null) }
    var libraries by remember { mutableStateOf<List<Library>>(emptyList()) }
    var activeLibraryId by remember { mutableStateOf<Int?>(null) }
    val api = remember(server, token) {
        if (token != null && (server.startsWith("http://") || server.startsWith("https://"))) {
            runCatching {
                ApiFactory.create(server) {
                    store.clearToken()
                    token = null
                    serverVersion = null
                    loginMessage = "Session expired. The server was updated or your login session is no longer valid. Please sign in again."
                    screen = Screen.LOGIN
                }
            }.getOrNull()
        } else null
    }

    LaunchedEffect(api, token) {
        if (api != null && token != null) {
            val savedVersion = store.lastServerVersion
            val statusResult = runCatching { api.status() }
            val currentStatus = statusResult.getOrNull()
            if (currentStatus != null) {
                serverVersion = currentStatus.serverVersion
                if (savedVersion != null && currentStatus.serverVersion != savedVersion) {
                    store.clearToken()
                    token = null
                    libraries = emptyList()
                    activeLibraryId = null
                    loginMessage = "Homebuster server was updated from v$savedVersion to v${currentStatus.serverVersion}. Please sign in again."
                    screen = Screen.LOGIN
                    return@LaunchedEffect
                }
                if (savedVersion == null) store.lastServerVersion = currentStatus.serverVersion
            }
            runCatching { api.libraries("Bearer $token").libraries }.onSuccess { loaded ->
                libraries = loaded
                if (activeLibraryId == null || loaded.none { it.id == activeLibraryId }) {
                    activeLibraryId = loaded.firstOrNull()?.id
                }
            }
        } else {
            libraries = emptyList()
            activeLibraryId = null
        }
    }
    val activeLibrary = libraries.firstOrNull { it.id == activeLibraryId } ?: libraries.firstOrNull()

    val navigateBack: () -> Unit = {
        screen = when (screen) {
            Screen.DETAILS -> detailsReturnScreen
            Screen.COLLECTIONS, Screen.LOANS, Screen.MORE, Screen.SCANNER, Screen.BARCODE_RESULT -> Screen.LIBRARY
            Screen.COLLECTION_DETAIL -> Screen.COLLECTIONS
            Screen.SHELF_DETAIL -> Screen.MORE
            Screen.LOAN_FORM -> Screen.DETAILS
            else -> screen
        }
    }
    BackHandler(enabled = screen != Screen.LOGIN && screen != Screen.LIBRARY) { navigateBack() }

    Surface(Modifier.fillMaxSize().systemBarsPadding(), color = HbBackground) {
        when (screen) {
            Screen.LOGIN -> LoginScreen(server, { server = it }, loginMessage, localNetworkGranted, {
                if (Build.VERSION.SDK_INT >= 37) localNetworkPermissionLauncher.launch(Manifest.permission.ACCESS_LOCAL_NETWORK)
            }) { normalizedServer, newToken, detectedVersion ->
                store.serverUrl = normalizedServer
                store.token = newToken
                server = normalizedServer
                token = newToken
                serverVersion = detectedVersion
                store.lastServerVersion = detectedVersion
                loginMessage = null
                screen = Screen.LIBRARY
            }
            Screen.LIBRARY -> LibraryScreen(
                api!!, token!!, serverVersion, libraries, activeLibrary,
                onLibrarySelected = { activeLibraryId = it.id },
                onMovie = { selected = it; detailsReturnScreen = Screen.LIBRARY; screen = Screen.DETAILS },
                onCollections = { screen = Screen.COLLECTIONS },
                onLoans = { screen = Screen.LOANS },
                onMore = { screen = Screen.MORE },
                onScan = { screen = Screen.SCANNER },
                onLogout = { store.clear(); token = null; serverVersion = null; libraries = emptyList(); activeLibraryId = null; screen = Screen.LOGIN }
            )
            Screen.DETAILS -> MovieDetailScreen(
                api!!, token!!, selected!!, activeLibrary,
                onLoan = { selectedCopy = it; screen = Screen.LOAN_FORM },
                onBack = navigateBack
            )
            Screen.COLLECTIONS -> CollectionsScreen(
                api!!, token!!, activeLibrary,
                onCollection = { selectedCollection = it; screen = Screen.COLLECTION_DETAIL },
                onBack = navigateBack
            )
            Screen.COLLECTION_DETAIL -> CollectionDetailScreen(api!!, token!!, selectedCollection!!, onMovie = { selected = it; detailsReturnScreen = Screen.COLLECTION_DETAIL; screen = Screen.DETAILS }, onBack = navigateBack)
            Screen.LOANS -> LoansScreen(api!!, token!!, navigateBack)
            Screen.LOAN_FORM -> LoanFormScreen(api!!, token!!, selectedCopy!!, navigateBack)
            Screen.MORE -> MoreScreen(
                api!!, token!!, libraries, activeLibrary, { activeLibraryId = it.id },
                onShelf = { selectedShelf = it; screen = Screen.SHELF_DETAIL },
                onBack = navigateBack
            )
            Screen.SHELF_DETAIL -> ShelfDetailScreen(api!!, token!!, store, selectedShelf!!, onMovie = { selected = it; detailsReturnScreen = Screen.SHELF_DETAIL; screen = Screen.DETAILS }, onBack = navigateBack)
            Screen.SCANNER -> ScannerScreen(onCode = { code ->
                scanned = BarcodeResponse(status = "loading", upc = code, movie = null, product = null, lookup = null)
                screen = Screen.BARCODE_RESULT
            }, onBack = navigateBack)
            Screen.BARCODE_RESULT -> BarcodeResultScreen(
                api!!, token!!, scanned?.upc.orEmpty(),
                activeLibrary = activeLibrary,
                initialMediaType = activeLibrary?.defaultMediaType ?: "movie",
                onLoaded = { scanned = it },
                onBack = navigateBack
            )
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
    loginMessage: String?,
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
            loginMessage?.let {
                HomebusterPanel { Text(it, color = HbWarning) }
                Spacer(Modifier.height(12.dp))
            }
            HomebusterPanel {
                Text("Homebuster", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.ExtraBold)
                Text("Your movie & TV library, in your pocket.", color = HbMuted)
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
private fun LibraryScreen(
    api: HomebusterApi, token: String, serverVersion: String?,
    libraries: List<Library>, activeLibrary: Library?, onLibrarySelected: (Library) -> Unit,
    onMovie: (MovieGroup) -> Unit, onCollections: () -> Unit, onLoans: () -> Unit, onMore: () -> Unit, onScan: () -> Unit, onLogout: () -> Unit
) {
    var movies by remember { mutableStateOf<List<Movie>>(emptyList()) }
    var query by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var libraryMenuExpanded by remember { mutableStateOf(false) }
    LaunchedEffect(query, activeLibrary?.id) {
        try {
            movies = api.movies("Bearer $token", query.ifBlank { null }, activeLibrary?.id).movies
            error = null
        } catch (e: Exception) { error = friendly(e) }
    }
    val groups = remember(movies) { groupMovies(movies) }
    Column(Modifier.fillMaxSize()) {
        HomebusterTopBar("App v${BuildConfig.VERSION_NAME} • Server v${serverVersion ?: "unknown"}", "Log out", onLogout)
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            if (libraries.isNotEmpty()) {
                Box {
                    OutlinedButton(onClick = { libraryMenuExpanded = true }, modifier = Modifier.fillMaxWidth()) {
                        Text("Library: ${activeLibrary?.name ?: libraries.first().name}")
                    }
                    DropdownMenu(expanded = libraryMenuExpanded, onDismissRequest = { libraryMenuExpanded = false }) {
                        libraries.forEach { library ->
                            DropdownMenuItem(
                                text = { Text("${library.name} • ${when (library.defaultMediaType) { "tv" -> "TV"; "collection" -> "Box Sets"; else -> "Movies" }}") },
                                onClick = { libraryMenuExpanded = false; onLibrarySelected(library) }
                            )
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
            }
            OutlinedTextField(query, { query = it }, label = { Text("Search this library") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Button(onClick = {}, modifier = Modifier.weight(1f)) { Text("Media") }
                OutlinedButton(onClick = onCollections, modifier = Modifier.weight(1f)) { Text("Collections") }
                OutlinedButton(onClick = onLoans, modifier = Modifier.weight(1f)) { Text("Loans") }
                OutlinedButton(onClick = onMore, modifier = Modifier.weight(1f)) { Text("More") }
            }
            Spacer(Modifier.height(8.dp))
            Button(onClick = onScan, modifier = Modifier.fillMaxWidth()) { Text("Scan barcode") }
            error?.let { Spacer(Modifier.height(10.dp)); HomebusterErrorCard(it) }
        }
        if (groups.isEmpty() && error == null) {
            Box(Modifier.fillMaxSize().padding(horizontal = 16.dp)) { HomebusterEmptyState(if (query.isBlank()) "No movies in this library yet." else "No movies match your search.") }
        } else {
            LazyVerticalGrid(
                GridCells.Adaptive(155.dp), modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)
            ) { items(groups, key = { it.key }) { group -> HomebusterMovieCard(group) { onMovie(group) } } }
        }
    }
}

@Composable
private fun MovieDetailScreen(
    api: HomebusterApi,
    token: String,
    group: MovieGroup,
    activeLibrary: Library?,
    onLoan: (Movie) -> Unit,
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val formatChoices = listOf("Blu-ray", "Blu-ray + DVD", "4K", "4K UHD", "DVD", "HD DVD", "VHS", "Other")
    var selectedCopy by remember(group.key) { mutableStateOf(group.copies.first()) }
    var shelves by remember { mutableStateOf<List<Shelf>>(emptyList()) }
    var showMore by remember { mutableStateOf(false) }
    var actionMessage by remember { mutableStateOf<String?>(null) }
    var editTitle by remember(selectedCopy.id) { mutableStateOf(selectedCopy.title) }
    var editFormat by remember(selectedCopy.id) { mutableStateOf(selectedCopy.format.takeIf { it in formatChoices } ?: "Other") }
    var editShelfId by remember(selectedCopy.id) { mutableStateOf(selectedCopy.shelfId) }
    var formatMenu by remember { mutableStateOf(false) }
    var shelfMenu by remember { mutableStateOf(false) }

    LaunchedEffect(activeLibrary?.id) {
        runCatching { api.shelves("Bearer $token").shelves }
            .onSuccess { all -> shelves = all.filter { activeLibrary == null || it.libraryId == activeLibrary.id } }
    }

    val movie = group.primary
    val selectedShelfName = shelves.firstOrNull { it.id == selectedCopy.shelfId }?.name ?: "Unassigned"

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { HomebusterScreenHeader("Media details", onBack) }
        item {
            HomebusterPanel {
                AsyncImage(
                    model = movie.posterUrl,
                    contentDescription = movie.title,
                    modifier = Modifier.fillMaxWidth().heightIn(max = 520.dp).aspectRatio(2f / 3f),
                    contentScale = ContentScale.Fit
                )
                Spacer(Modifier.height(14.dp))
                Text(movie.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    movie.year?.let { HomebusterMetaChip(it.toString()) }
                    HomebusterMetaChip(if (movie.mediaType == "tv") "TV" else "Movie", HbAccent)
                }
                if (group.copies.size > 1) {
                    Spacer(Modifier.height(8.dp))
                    Text(group.formatsSummary, color = HbMuted, style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        item {
            HomebusterPanel {
                Text(if (group.copies.size == 1) "Physical copy" else "Choose physical copy", fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                group.copies.forEach { copy ->
                    val label = buildString {
                        append(copy.format.ifBlank { "Unknown" })
                        copy.version?.takeIf { it.isNotBlank() }?.let { append(" • $it") }
                        if (copy.loanState != "available") append(" • On loan")
                    }
                    if (copy.id == selectedCopy.id) {
                        Button(onClick = { selectedCopy = copy }, modifier = Modifier.fillMaxWidth()) { Text(label) }
                    } else {
                        OutlinedButton(onClick = { selectedCopy = copy }, modifier = Modifier.fillMaxWidth()) { Text(label) }
                    }
                    Spacer(Modifier.height(6.dp))
                }
                Text("Shelf: $selectedShelfName", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = { showMore = !showMore }, modifier = Modifier.fillMaxWidth()) {
                    Text("More Info")
                }
                if (showMore) {
                    Spacer(Modifier.height(10.dp))
                    Text("Physical metadata", fontWeight = FontWeight.Bold)
                    selectedCopy.upc?.takeIf { it.isNotBlank() }?.let { Text("UPC: $it", color = HbMuted) }
                    selectedCopy.version?.takeIf { it.isNotBlank() }?.let { Text("Edition: $it", color = HbMuted) }
                    selectedCopy.country?.takeIf { it.isNotBlank() }?.let { Text("Country: $it", color = HbMuted) }
                    selectedCopy.language?.takeIf { it.isNotBlank() }?.let { Text("Language: $it", color = HbMuted) }
                    selectedCopy.region?.takeIf { it.isNotBlank() }?.let { Text("Region: $it", color = HbMuted) }
                    selectedCopy.discCount?.let { Text("Disc count: $it", color = HbMuted) }
                    selectedCopy.tmdbId?.let { Text("TMDb ID: $it", color = HbMuted) }
                    Text("Status: ${selectedCopy.status}", color = HbMuted)
                    Text("Loan state: ${selectedCopy.loanState.replace('_', ' ')}", color = HbMuted)
                    selectedCopy.parentBoxSetName?.let { Text("Box set: $it", color = HbMuted) }
                    selectedCopy.notes?.takeIf { it.isNotBlank() }?.let {
                        Spacer(Modifier.height(8.dp))
                        Text("Notes", fontWeight = FontWeight.Bold)
                        Text(it, color = HbMuted)
                    }
                    if (selectedCopy.overview.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text("Overview", fontWeight = FontWeight.Bold)
                        Text(selectedCopy.overview, color = HbMuted)
                    }
                }
            }
        }

        if (activeLibrary?.role != "viewer") item {
            HomebusterPanel {
                Text("Edit media", fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(editTitle, { editTitle = it }, label = { Text("Title") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Box {
                    OutlinedButton(onClick = { formatMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text("Format: $editFormat")
                    }
                    DropdownMenu(expanded = formatMenu, onDismissRequest = { formatMenu = false }) {
                        formatChoices.forEach { choice ->
                            DropdownMenuItem(
                                text = { Text(choice) },
                                onClick = { editFormat = choice; formatMenu = false }
                            )
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Box {
                    val shelfLabel = shelves.firstOrNull { it.id == editShelfId }?.name ?: "Unassigned"
                    OutlinedButton(onClick = { shelfMenu = true }, modifier = Modifier.fillMaxWidth()) {
                        Text("Shelf: $shelfLabel")
                    }
                    DropdownMenu(expanded = shelfMenu, onDismissRequest = { shelfMenu = false }) {
                        DropdownMenuItem(text = { Text("Unassigned") }, onClick = { editShelfId = null; shelfMenu = false })
                        shelves.forEach { shelf ->
                            DropdownMenuItem(text = { Text(shelf.name) }, onClick = { editShelfId = shelf.id; shelfMenu = false })
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                Button(
                    enabled = editTitle.isNotBlank(),
                    onClick = {
                        scope.launch {
                            runCatching {
                                api.updateMovie(
                                    "Bearer $token",
                                    selectedCopy.id,
                                    UpdateMovieRequest(title = editTitle, format = editFormat, shelfId = editShelfId)
                                )["movie"]!!
                            }.onSuccess {
                                selectedCopy = it
                                actionMessage = "Saved"
                            }.onFailure { actionMessage = friendly(it as Exception) }
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Save changes") }
                Spacer(Modifier.height(8.dp))
                Button(onClick = { onLoan(selectedCopy) }, modifier = Modifier.fillMaxWidth()) {
                    Text("Loan Media")
                }
                actionMessage?.let { Spacer(Modifier.height(8.dp)); Text(it, color = HbMuted) }
            }
        }
    }
}

@Composable
private fun CollectionsScreen(
    api: HomebusterApi,
    token: String,
    activeLibrary: Library?,
    onCollection: (CollectionItem) -> Unit,
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var newName by remember { mutableStateOf("") }
    var data by remember { mutableStateOf<List<CollectionItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(activeLibrary?.id) {
        runCatching { api.collections("Bearer $token").collections }
            .onSuccess { all -> data = all.filter { activeLibrary == null || it.libraryId == activeLibrary.id } }
            .onFailure { error = friendly(it as Exception) }
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { HomebusterScreenHeader("Collections", onBack) }
        if (activeLibrary != null && activeLibrary.role != "viewer") item {
            HomebusterPanel {
                Text("Create collection", fontWeight = FontWeight.Bold)
                OutlinedTextField(newName, { newName = it }, label = { Text("Collection name") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Button(
                    enabled = newName.isNotBlank(),
                    onClick = {
                        scope.launch {
                            runCatching { api.createCollection("Bearer $token", CreateCollectionRequest(activeLibrary.id, newName)) }
                                .onSuccess { created ->
                                    data = data + created["collection"]!!
                                    newName = ""
                                }
                                .onFailure { error = friendly(it as Exception) }
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Create") }
            }
        }
        error?.let { item { HomebusterErrorCard(it) } }
        if (data.isEmpty() && error == null) item { HomebusterEmptyState("No collections yet.") }
        items(data, key = { it.id }) { c ->
            OutlinedButton(onClick = { onCollection(c) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.fillMaxWidth()) {
                    Text(c.name, fontWeight = FontWeight.Bold)
                    Text("${c.movieCount} media items", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun CollectionDetailScreen(
    api: HomebusterApi,
    token: String,
    collection: CollectionItem,
    onMovie: (MovieGroup) -> Unit,
    onBack: () -> Unit
) {
    var movies by remember { mutableStateOf<List<Movie>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(collection.id) {
        runCatching { api.collectionMovies("Bearer $token", collection.id).movies }
            .onSuccess { movies = it }
            .onFailure { error = friendly(it as Exception) }
    }
    val groups = remember(movies) { groupMovies(movies) }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(16.dp)) {
            HomebusterScreenHeader(collection.name, onBack)
            error?.let { HomebusterErrorCard(it) }
        }
        if (groups.isEmpty() && error == null) {
            HomebusterEmptyState("No media in this collection.")
        } else {
            LazyVerticalGrid(
                GridCells.Adaptive(155.dp),
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                items(groups, key = { it.key }) { group ->
                    HomebusterMovieCard(group) { onMovie(group) }
                }
            }
        }
    }
}

@Composable
private fun LoansScreen(api: HomebusterApi, token: String, onBack: () -> Unit) {
    var data by remember { mutableStateOf<List<Loan>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        runCatching { api.loans("Bearer $token").loans }
            .onSuccess { data = it }
            .onFailure { error = friendly(it as Exception) }
    }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { HomebusterScreenHeader("Loans", onBack) }
        error?.let { item { HomebusterErrorCard(it) } }
        if (data.isEmpty() && error == null) item { HomebusterEmptyState("No loan history yet.") }
        items(data, key = { it.id }) { loan ->
            HomebusterPanel {
                Text(loan.title, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                if (loan.returnedAt == null) Text("Loaned to ${loan.borrower}", color = HbWarning)
                else Text("Returned ${loan.returnedAt}", color = HbGood)
                Text("Loaned ${loan.loanedAt}", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                if (loan.phone.isNotBlank()) Text("Phone: ${loan.phone}", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                if (loan.notes.isNotBlank()) Text(loan.notes, color = HbMuted, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun LoanFormScreen(
    api: HomebusterApi,
    token: String,
    movie: Movie,
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var borrower by remember(movie.id) { mutableStateOf("") }
    var phone by remember(movie.id) { mutableStateOf("") }
    var loanedDate by remember(movie.id) { mutableStateOf("") }
    var notes by remember(movie.id) { mutableStateOf("") }
    var history by remember { mutableStateOf<List<Loan>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var refresh by remember { mutableIntStateOf(0) }

    LaunchedEffect(movie.id, refresh) {
        runCatching { api.loans("Bearer $token").loans.filter { it.movieId == movie.id } }
            .onSuccess { history = it }
            .onFailure { error = friendly(it as Exception) }
    }
    val active = history.firstOrNull { it.returnedAt == null }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { HomebusterScreenHeader("Loan media", onBack) }
        item {
            HomebusterPanel {
                Text(movie.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(listOfNotNull(movie.format, movie.version).joinToString(" • "), color = HbMuted)
                movie.upc?.let { Text("UPC $it", color = HbMuted, style = MaterialTheme.typography.bodySmall) }
            }
        }
        error?.let { item { HomebusterErrorCard(it) } }
        message?.let { item { HomebusterPanel { Text(it, color = HbGood) } } }

        if (active != null) {
            item {
                HomebusterPanel {
                    Text("Currently on loan", fontWeight = FontWeight.Bold)
                    Text("Loaned to ${active.borrower}", color = HbWarning)
                    Text("Date: ${active.loanedAt}", color = HbMuted)
                    if (active.phone.isNotBlank()) Text("Phone: ${active.phone}", color = HbMuted)
                    if (active.notes.isNotBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text("Notes", fontWeight = FontWeight.Bold)
                        Text(active.notes, color = HbMuted)
                    }
                    Spacer(Modifier.height(10.dp))
                    Button(
                        onClick = {
                            scope.launch {
                                runCatching { api.returnMovie("Bearer $token", movie.id) }
                                    .onSuccess { message = "Marked returned"; refresh++ }
                                    .onFailure { error = friendly(it as Exception) }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("Mark Returned") }
                }
            }
        } else {
            item {
                HomebusterPanel {
                    Text("Loan details", fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(borrower, { borrower = it }, label = { Text("Loaned to") }, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(phone, { phone = it }, label = { Text("Phone (optional)") }, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        loanedDate, { loanedDate = it },
                        label = { Text("Date") },
                        placeholder = { Text("YYYY-MM-DD • blank = today") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(notes, { notes = it }, label = { Text("Notes (optional)") }, modifier = Modifier.fillMaxWidth(), minLines = 3)
                    Spacer(Modifier.height(10.dp))
                    Button(
                        enabled = borrower.isNotBlank(),
                        onClick = {
                            scope.launch {
                                runCatching {
                                    api.loanMovie(
                                        "Bearer $token",
                                        movie.id,
                                        LoanMovieRequest(
                                            borrower = borrower,
                                            phone = phone.ifBlank { null },
                                            loanedDate = loanedDate.ifBlank { null },
                                            notes = notes.ifBlank { null }
                                        )
                                    )
                                }.onSuccess {
                                    message = "Loan recorded"
                                    refresh++
                                }.onFailure { error = friendly(it as Exception) }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("Loan Movie") }
                }
            }
        }

        if (history.isNotEmpty()) {
            item { Text("Loan history", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
            items(history, key = { it.id }) { loan ->
                HomebusterPanel {
                    Text("${loan.borrower} • ${loan.loanedAt}", fontWeight = FontWeight.Bold)
                    Text(if (loan.returnedAt == null) "Currently out" else "Returned ${loan.returnedAt}", color = HbMuted)
                }
            }
        }
    }
}

@Composable
private fun MoreScreen(
    api: HomebusterApi,
    token: String,
    libraries: List<Library>,
    activeLibrary: Library?,
    onLibrarySelected: (Library) -> Unit,
    onShelf: (Shelf) -> Unit,
    onBack: () -> Unit
) {
    var shelves by remember { mutableStateOf<List<Shelf>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(activeLibrary?.id) {
        runCatching { api.shelves("Bearer $token").shelves.filter { activeLibrary == null || it.libraryId == activeLibrary.id } }
            .onSuccess { shelves = it }
            .onFailure { error = friendly(it as Exception) }
    }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { HomebusterScreenHeader("More", onBack) }
        item {
            HomebusterPanel {
                Text("Library", fontWeight = FontWeight.Bold)
                libraries.forEach { library ->
                    if (library.id == activeLibrary?.id) {
                        Button(onClick = {}, modifier = Modifier.fillMaxWidth()) { Text(library.name) }
                    } else {
                        OutlinedButton(onClick = { onLibrarySelected(library) }, modifier = Modifier.fillMaxWidth()) { Text(library.name) }
                    }
                }
            }
        }
        item { Text("Shelves", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
        error?.let { item { HomebusterErrorCard(it) } }
        if (shelves.isEmpty() && error == null) item { HomebusterEmptyState("No shelves in this library.") }
        items(shelves, key = { it.id }) { shelf ->
            OutlinedButton(onClick = { onShelf(shelf) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.fillMaxWidth()) {
                    Text(shelf.name, fontWeight = FontWeight.Bold)
                    shelf.description?.takeIf { it.isNotBlank() }?.let { Text(it, color = HbMuted) }
                }
            }
        }
    }
}

@Composable
private fun HomebusterShelfFrontCase(group: MovieGroup, onClick: () -> Unit) {
    val movie = group.primary
    val format = movie.format.ifBlank { "Media" }
    val normalized = format.lowercase()
    val isUhd = normalized.contains("4k") || normalized.contains("ultra hd") || normalized.contains("uhd")
    val isBluray = normalized.contains("blu-ray") || normalized.contains("blu ray")
    val isDvd = Regex("\\bdvd\\b").containsMatchIn(normalized)
    val (casePlasticDark, casePlastic, caseGlow) = when {
        isUhd -> Triple(Color(0xFF020303), Color(0xFF151719), Color(0xFF34383C))
        isBluray -> Triple(Color(0xFF0B3767), Color(0xFF176CC0), Color(0xFF55A9EF))
        isDvd -> Triple(Color(0xFF08090B), Color(0xFF25272B), Color(0xFF50545A))
        else -> Triple(Color(0xFF15191F), Color(0xFF414956), Color(0xFF687384))
    }

    Column(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            // The web case is designed at 306px wide. Scale every shell measurement
            // from that same reference instead of treating CSS pixels as fixed dp.
            val caseWidth = maxWidth
            val topInset = caseWidth * (43f / 306f)
            val sideInset = caseWidth * (10f / 306f)
            val bottomInset = caseWidth * (13f / 306f)
            val ridgeTop = caseWidth * (7f / 306f)
            val ridgeHeight = caseWidth * (29f / 306f)
            val hingeTop = caseWidth * (48f / 306f)
            val hingeBottom = caseWidth * (18f / 306f)
            val hingeWidth = caseWidth * (5f / 306f)
            val shellRadius = caseWidth * (12f / 306f)

            Box(
                Modifier.fillMaxWidth()
                    .graphicsLayer { shadowElevation = 18f }
                    .clip(RoundedCornerShape(shellRadius, shellRadius, shellRadius * .67f, shellRadius * .67f))
                    .background(Brush.horizontalGradient(listOf(casePlasticDark, casePlastic, caseGlow, casePlastic, casePlasticDark)))
                    .padding(start = sideInset, top = topInset, end = sideInset, bottom = bottomInset)
            ) {
                Box(
                    Modifier.align(Alignment.TopCenter)
                        .offset(y = -(topInset - ridgeTop))
                        .fillMaxWidth()
                        .height(ridgeHeight)
                        .clip(RoundedCornerShape(shellRadius * .58f))
                        .background(Brush.verticalGradient(listOf(Color(0x38FFFFFF), Color(0x08FFFFFF), Color(0x16000000), Color.Transparent)))
                )
                Box(
                    Modifier.align(Alignment.CenterStart)
                        .offset(x = -(sideInset * .6f), y = (hingeTop - hingeBottom) * .04f)
                        .width(hingeWidth)
                        .fillMaxHeight()
                        .clip(RoundedCornerShape(4.dp))
                        .background(Brush.horizontalGradient(listOf(Color(0x70000000), Color(0x42FFFFFF), Color(0x50000000))))
                )
                Box(
                    Modifier.fillMaxWidth()
                        .padding(caseWidth * (3f / 306f))
                        .background(Color(0xFF09101A))
                        .aspectRatio(2f / 3f),
                    contentAlignment = Alignment.Center
                ) {
                    if (movie.posterUrl != null) {
                        AsyncImage(
                            model = movie.posterUrl,
                            contentDescription = movie.title,
                            modifier = Modifier.matchParentSize(),
                            contentScale = ContentScale.Crop
                        )
                    } else {
                        Text("🎬", style = MaterialTheme.typography.headlineLarge, color = Color(0xFF68758D))
                    }
                }
                Box(
                    Modifier.align(Alignment.TopCenter)
                        .offset(y = -(topInset - ridgeTop))
                        .fillMaxWidth()
                        .height(ridgeHeight),
                    contentAlignment = Alignment.Center
                ) {
                    val singleLogoHeight = ridgeHeight * .96f
                    val comboLogoHeight = ridgeHeight * .88f
                    val logoHeight = if ((if (isUhd) 1 else 0) + (if (isBluray) 1 else 0) + (if (isDvd) 1 else 0) > 1) comboLogoHeight else singleLogoHeight
                    Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (isUhd) Image(
                            painter = painterResource(R.drawable.media_logo_uhd_bluray),
                            contentDescription = "Ultra HD Blu-ray",
                            modifier = Modifier.height(if (isBluray || isDvd) comboLogoHeight else singleLogoHeight).width(logoHeight * 2.9f).graphicsLayer { alpha = .98f },
                            contentScale = ContentScale.Fit,
                            colorFilter = ColorFilter.tint(Color.White)
                        )
                        if (isBluray) Image(
                            painter = painterResource(R.drawable.media_logo_bluray),
                            contentDescription = "Blu-ray Disc",
                            modifier = Modifier.height(if (isUhd || isDvd) comboLogoHeight else singleLogoHeight).width(logoHeight * 2.3f).graphicsLayer { alpha = .98f },
                            contentScale = ContentScale.Fit,
                            colorFilter = ColorFilter.tint(Color.White)
                        )
                        if (isDvd) Image(
                            painter = painterResource(R.drawable.media_logo_dvd_video),
                            contentDescription = "DVD Video",
                            modifier = Modifier.height(if (isUhd || isBluray) comboLogoHeight else singleLogoHeight).width(logoHeight * 2.0f).graphicsLayer { alpha = .98f },
                            contentScale = ContentScale.Fit,
                            colorFilter = ColorFilter.tint(Color.White)
                        )
                        if (!isUhd && !isBluray && !isDvd) Text(format, color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelSmall)
                    }
                }
                Box(
                    Modifier.matchParentSize()
                        .clip(RoundedCornerShape(shellRadius, shellRadius, shellRadius * .67f, shellRadius * .67f))
                        .background(Brush.verticalGradient(listOf(Color(0x12FFFFFF), Color.Transparent, Color(0x30000000))))
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(movie.title, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
        movie.year?.let { Text(it.toString(), color = HbMuted, style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun HomebusterShelfSpine(group: MovieGroup, onClick: () -> Unit) {
    val movie = group.primary
    val format = movie.format.ifBlank { "Media" }
    val caseColor = when (format) {
        "Blu-ray", "Blu-ray + DVD" -> Color(0xFF176CC0)
        "4K", "4K UHD" -> Color(0xFF17191E)
        "HD DVD" -> Color(0xFF8E2025)
        "VHS" -> Color(0xFF292929)
        "DVD" -> Color(0xFF20252C)
        else -> Color(0xFF39414D)
    }
    val caseHighlight = when (format) {
        "Blu-ray", "Blu-ray + DVD" -> Color(0xFF55A9EF)
        "4K", "4K UHD" -> Color(0xFF5B5F67)
        "HD DVD" -> Color(0xFFD24A50)
        else -> Color(0xFF737E8E)
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(206.dp)
            .padding(bottom = 4.dp)
            .graphicsLayer { shadowElevation = 7f }
            .clip(RoundedCornerShape(3.dp))
            .background(Brush.horizontalGradient(listOf(caseColor, caseHighlight, caseColor)))
            .clickable(onClick = onClick)
    ) {
        movie.posterUrl?.let { poster ->
            AsyncImage(
                model = poster,
                contentDescription = null,
                modifier = Modifier.matchParentSize(),
                contentScale = ContentScale.Crop,
                alpha = 0.38f
            )
        }
        Box(
            Modifier.matchParentSize().background(
                Brush.horizontalGradient(
                    listOf(Color(0xB0000000), Color(0x18000000), Color(0x90000000))
                )
            )
        )
        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                Modifier.fillMaxWidth().height(19.dp).background(caseColor),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    format.uppercase(),
                    color = Color.White,
                    fontWeight = FontWeight.Black,
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Clip
                )
            }
            Spacer(Modifier.height(7.dp))
            Text(
                movie.title,
                modifier = Modifier
                    .weight(1f)
                    .graphicsLayer { rotationZ = 90f },
                color = Color.White,
                fontWeight = FontWeight.Black,
                style = MaterialTheme.typography.labelSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun ShelfDetailScreen(
    api: HomebusterApi,
    token: String,
    store: SessionStore,
    shelf: Shelf,
    onMovie: (MovieGroup) -> Unit,
    onBack: () -> Unit
) {
    var movies by remember { mutableStateOf<List<Movie>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var shelfViewMode by remember(shelf.id) {
        mutableStateOf(if (store.shelfViewMode == "spines") ShelfViewMode.SPINES else ShelfViewMode.FRONT)
    }
    LaunchedEffect(shelf.id) {
        runCatching { api.shelfMovies("Bearer $token", shelf.id).movies }
            .onSuccess { movies = it }
            .onFailure { error = friendly(it as Exception) }
    }
    val groups = remember(movies) { groupMovies(movies) }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(16.dp)) {
            HomebusterScreenHeader(shelf.name, onBack)
            shelf.description?.takeIf { it.isNotBlank() }?.let { Text(it, color = HbMuted) }
            error?.let { HomebusterErrorCard(it) }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (shelfViewMode == ShelfViewMode.FRONT) {
                    Button(onClick = {}) { Text("Front Covers") }
                } else {
                    OutlinedButton(onClick = { shelfViewMode = ShelfViewMode.FRONT; store.shelfViewMode = "front" }) { Text("Front Covers") }
                }
                if (shelfViewMode == ShelfViewMode.SPINES) {
                    Button(onClick = {}) { Text("Spines") }
                } else {
                    OutlinedButton(onClick = { shelfViewMode = ShelfViewMode.SPINES; store.shelfViewMode = "spines" }) { Text("Spines") }
                }
            }
        }
        if (groups.isEmpty() && error == null) {
            HomebusterEmptyState("No media on this shelf.")
        } else {
            if (shelfViewMode == ShelfViewMode.FRONT) {
                LazyVerticalGrid(
                    GridCells.Adaptive(145.dp),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 14.dp, end = 14.dp, top = 8.dp, bottom = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                    verticalArrangement = Arrangement.spacedBy(18.dp)
                ) {
                    items(groups, key = { it.key }) { group ->
                        HomebusterShelfFrontCase(group) { onMovie(group) }
                    }
                }
            } else {
                LazyVerticalGrid(
                    GridCells.Adaptive(48.dp),
                    modifier = Modifier.fillMaxSize()
                        .background(Brush.verticalGradient(listOf(Color(0xFF24170F), Color(0xFF5A3822), Color(0xFF21140D)))),
                    contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 14.dp, bottom = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(3.dp),
                    verticalArrangement = Arrangement.spacedBy(18.dp)
                ) {
                    items(groups, key = { it.key }) { group ->
                        HomebusterShelfSpine(group) { onMovie(group) }
                    }
                }
            }
        }
    }
}

@Composable
private fun BarcodeResultScreen(
    api: HomebusterApi,
    token: String,
    upc: String,
    activeLibrary: Library?,
    initialMediaType: String,
    onLoaded: (BarcodeResponse) -> Unit,
    onBack: () -> Unit
) {
    var result by remember(upc, initialMediaType) { mutableStateOf<BarcodeResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var addError by remember { mutableStateOf<String?>(null) }
    var addingTmdbId by remember { mutableStateOf<Int?>(null) }
    var addedMovie by remember { mutableStateOf<Movie?>(null) }
    var addedBoxSetTitle by remember { mutableStateOf<String?>(null) }
    var mediaType by remember(upc, initialMediaType) {
        mutableStateOf(initialMediaType.takeIf { it in setOf("movie", "tv", "collection") } ?: "movie")
    }
    val scope = rememberCoroutineScope()

    LaunchedEffect(upc, mediaType, activeLibrary?.id) {
        result = null
        error = null
        try {
            result = api.barcode("Bearer $token", upc, mediaType, activeLibrary?.id)
            onLoaded(result!!)
        } catch (e: HttpException) {
            error = if (e.code() == 404) "Barcode $upc is not in this library and the server could not identify it." else friendly(e)
        } catch (e: Exception) {
            error = friendly(e)
        }
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { HomebusterScreenHeader("Barcode lookup", onBack) }
        item {
            Text("UPC $upc", color = HbMuted, style = MaterialTheme.typography.bodySmall)
            activeLibrary?.let { Text("Library: ${it.name}", color = HbMuted, style = MaterialTheme.typography.bodySmall) }
        }
        item {
            HomebusterPanel {
                Text("TMDb search type", fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (mediaType == "movie") Button(onClick = { mediaType = "movie" }, modifier = Modifier.weight(1f)) { Text("Movie") }
                    else OutlinedButton(onClick = { mediaType = "movie" }, modifier = Modifier.weight(1f)) { Text("Movie") }
                    if (mediaType == "tv") Button(onClick = { mediaType = "tv" }, modifier = Modifier.weight(1f)) { Text("TV") }
                    else OutlinedButton(onClick = { mediaType = "tv" }, modifier = Modifier.weight(1f)) { Text("TV") }
                    if (mediaType == "collection") Button(onClick = { mediaType = "collection" }, modifier = Modifier.weight(1f)) { Text("Box Set") }
                    else OutlinedButton(onClick = { mediaType = "collection" }, modifier = Modifier.weight(1f)) { Text("Box Set") }
                }
                Text(
                    "This scan starts with the library default. Changing it applies only to this lookup.",
                    color = HbMuted,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }

        addedMovie?.let { movie ->
            item {
                HomebusterPanel {
                    Text("Added to Homebuster", color = HbGood, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Text(movie.title, style = MaterialTheme.typography.titleLarge)
                    Text(listOfNotNull(movie.format, movie.version).joinToString(" • "), color = HbMuted)
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back to library") }
                }
            }
        }
        addedBoxSetTitle?.let { title ->
            item {
                HomebusterPanel {
                    Text("Added box set to Homebuster", color = HbGood, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Text(title, style = MaterialTheme.typography.titleLarge)
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back to library") }
                }
            }
        }
        addError?.let { item { HomebusterErrorCard(it) } }

        when (val r = result) {
            null -> item { if (error != null) HomebusterErrorCard(error!!) else HomebusterPanel { Text("Looking up barcode…", color = HbMuted) } }
            else -> if (r.status == "provider_not_found") {
                item {
                    HomebusterPanel {
                        Text("Local library", color = HbAccent, fontWeight = FontWeight.Bold)
                        Text("Not currently in this library", color = HbMuted)
                        Spacer(Modifier.height(12.dp))
                        Text("UPCitemdb", color = HbAccent, fontWeight = FontWeight.Bold)
                        Text(r.message ?: "UPCitemdb did not find a product for this barcode", color = HbWarning, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(8.dp))
                        Text("Homebuster can't search TMDb automatically because UPCitemdb didn't provide a title.", color = HbMuted)
                    }
                }
            } else if (r.status == "owned" && r.movie != null) {
                item {
                    HomebusterPanel {
                        Text("You already own this in the selected library.", color = HbGood, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(4.dp))
                        Text(r.movie.title, style = MaterialTheme.typography.titleLarge)
                        Text(listOfNotNull(r.movie.format, r.movie.version).joinToString(" • "), color = HbMuted)
                    }
                }
            } else if (r.status == "owned" && r.boxSet != null) {
                item {
                    HomebusterPanel {
                        Text("You already own this box set in the selected library.", color = HbGood, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(4.dp))
                        Text(r.boxSet.title, style = MaterialTheme.typography.titleLarge)
                    }
                }
            } else {
                item {
                    HomebusterPanel {
                        Text("Scanned product", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                        Text(r.product?.productTitle ?: "Product found", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        r.lookup?.let { lookup ->
                            Spacer(Modifier.height(12.dp))
                            Text("Homebuster detected", color = HbAccent, fontWeight = FontWeight.Bold)
                            val kind = when (mediaType) { "tv" -> "TV series"; "collection" -> "Movie box set"; else -> "Movie" }
                            Text("$kind: ${lookup.title}")
                            lookup.year?.let { Text("Year: $it") }
                            lookup.format?.takeIf { it.isNotBlank() }?.let { Text("Format: $it") }
                            lookup.language?.takeIf { it.isNotBlank() }?.let { Text("Language: $it") }
                            lookup.edition?.takeIf { it.isNotBlank() }?.let { Text("Version / Edition: $it") }
                            lookup.region?.takeIf { it.isNotBlank() }?.let { Text("Region: $it") }
                            lookup.discCount?.let { Text("Disc count: $it") }
                            lookup.distributor?.takeIf { it.isNotBlank() }?.let {
                                Spacer(Modifier.height(6.dp))
                                Text("Catalog/distributor removed from search: $it", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                            }
                            lookup.category?.takeIf { it.isNotBlank() }?.let {
                                Text("Category removed from search: $it", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                            }
                            Spacer(Modifier.height(10.dp))
                            Text("TMDb search: ${lookup.title}${lookup.year?.let { " ($it)" } ?: ""}", color = HbAccent)
                            if (lookup.attempts.size > 1) Text("Homebuster tried ${lookup.attempts.size} search variations.", color = HbMuted, style = MaterialTheme.typography.bodySmall)
                        }
                        Spacer(Modifier.height(8.dp))
                        val count = r.tmdbResults?.size ?: 0
                        Text(if (count == 0) "No TMDb matches found" else "$count TMDb matches", color = if (count == 0) HbWarning else HbGood)
                    }
                }

                items(r.tmdbResults.orEmpty(), key = { it.tmdbId }) { match ->
                    val isBest = r.bestMatch?.tmdbId == match.tmdbId || r.tmdbResults?.firstOrNull()?.tmdbId == match.tmdbId
                    HomebusterPanel {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            match.posterPath?.let {
                                AsyncImage(
                                    model = "https://image.tmdb.org/t/p/w185$it",
                                    contentDescription = match.title,
                                    modifier = Modifier.width(74.dp).aspectRatio(2f / 3f),
                                    contentScale = ContentScale.Crop
                                )
                            }
                            Column(Modifier.weight(1f)) {
                                if (isBest) { HomebusterMetaChip("Best match", HbGood); Spacer(Modifier.height(6.dp)) }
                                HomebusterMetaChip(when (match.mediaType) { "tv" -> "TV"; "collection" -> "Box Set"; else -> "Movie" }, HbAccent)
                                Spacer(Modifier.height(4.dp))
                                Text(match.title, fontWeight = FontWeight.Bold)
                                match.year?.let { Text(it.toString(), color = HbMuted) }
                                if (match.overview.isNotBlank()) Text(match.overview, color = HbMuted, style = MaterialTheme.typography.bodySmall, maxLines = 4)
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                        Button(
                            enabled = addedMovie == null && addedBoxSetTitle == null && addingTmdbId == null && activeLibrary != null,
                            onClick = {
                                addError = null
                                addingTmdbId = match.tmdbId
                                scope.launch {
                                    try {
                                        val libraryId = activeLibrary?.id ?: error("No active library selected")
                                        val lookup = r.lookup
                                        if (mediaType == "collection" || match.mediaType == "collection") {
                                            val details = api.collectionDetails("Bearer $token", match.tmdbId).collection
                                            val members = details.parts.map { part ->
                                                AddBoxSetMember(
                                                    tmdbId = part.id,
                                                    title = part.title,
                                                    year = part.releaseDate?.take(4)?.toIntOrNull(),
                                                    posterPath = part.posterPath,
                                                    position = part.position
                                                )
                                            }
                                            val response = api.addBoxSet(
                                                "Bearer $token",
                                                AddBoxSetRequest(
                                                    libraryId = libraryId,
                                                    barcode = r.upc ?: upc,
                                                    title = details.title.ifBlank { match.title },
                                                    tmdbCollectionId = details.id,
                                                    posterPath = details.posterPath ?: match.posterPath,
                                                    format = lookup?.format?.takeIf { it.isNotBlank() } ?: "Unknown",
                                                    version = lookup?.edition,
                                                    language = lookup?.language,
                                                    region = lookup?.region,
                                                    discCount = lookup?.discCount,
                                                    members = members
                                                )
                                            )
                                            addedBoxSetTitle = response.boxSet.title
                                        } else {
                                            val selectedMetadata = match.copyMetadata
                                            val response = api.addMovie(
                                                "Bearer $token",
                                                AddMovieRequest(
                                                    libraryId = libraryId,
                                                    tmdbId = match.tmdbId,
                                                    mediaType = match.mediaType.ifBlank { mediaType },
                                                    title = match.title,
                                                    year = match.year,
                                                    overview = match.overview,
                                                    posterPath = match.posterPath,
                                                    format = selectedMetadata?.format?.takeIf { it.isNotBlank() }
                                                        ?: lookup?.format?.takeIf { it.isNotBlank() } ?: "Unknown",
                                                    upc = r.upc ?: upc,
                                                    version = selectedMetadata?.edition ?: lookup?.edition,
                                                    language = selectedMetadata?.language ?: lookup?.language,
                                                    region = selectedMetadata?.region ?: lookup?.region,
                                                    discCount = selectedMetadata?.discCount ?: lookup?.discCount
                                                )
                                            )
                                            addedMovie = response["movie"]
                                        }
                                    } catch (e: Exception) {
                                        addError = friendly(e)
                                    } finally {
                                        addingTmdbId = null
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text(if (addingTmdbId == match.tmdbId) "Adding…" else "Add this copy") }
                    }
                }
            }
        }
    }
}
