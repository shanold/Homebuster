package com.homebuster.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import kotlinx.coroutines.launch
import retrofit2.HttpException

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme(colorScheme = darkColorScheme()) { HomebusterApp(SessionStore(this)) } }
    }
}

enum class Screen { LOGIN, LIBRARY, DETAILS, COLLECTIONS, LOANS, SCANNER, BARCODE_RESULT }

@Composable
fun HomebusterApp(store: SessionStore) {
    val context = LocalContext.current
    var localNetworkGranted by remember {
        mutableStateOf(
            Build.VERSION.SDK_INT < 37 ||
                context.checkSelfPermission(Manifest.permission.ACCESS_LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED
        )
    }
    val localNetworkPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> localNetworkGranted = granted }

    var server by remember { mutableStateOf(store.serverUrl ?: "") }
    var token by remember { mutableStateOf(store.token) }
    var serverVersion by remember { mutableStateOf<String?>(null) }
    var screen by remember { mutableStateOf(if (token == null || server.isBlank()) Screen.LOGIN else Screen.LIBRARY) }
    var selected by remember { mutableStateOf<Movie?>(null) }
    var scanned by remember { mutableStateOf<BarcodeResponse?>(null) }
    val api = remember(server) { if (server.startsWith("http://") || server.startsWith("https://")) ApiFactory.create(server) else null }

    when (screen) {
        Screen.LOGIN -> LoginScreen(
            server = server,
            onServer = { server = it },
            localNetworkGranted = localNetworkGranted,
            onRequestLocalNetwork = {
                if (Build.VERSION.SDK_INT >= 37) {
                    localNetworkPermissionLauncher.launch(Manifest.permission.ACCESS_LOCAL_NETWORK)
                }
            },
            onLoggedIn = { normalizedServer, newToken, detectedServerVersion ->
                store.serverUrl = normalizedServer
                store.token = newToken
                server = normalizedServer
                token = newToken
                serverVersion = detectedServerVersion
                screen = Screen.LIBRARY
            }
        )
        Screen.LIBRARY -> LibraryScreen(api!!, token!!, serverVersion, onMovie = { selected = it; screen = Screen.DETAILS }, onCollections = { screen = Screen.COLLECTIONS }, onLoans = { screen = Screen.LOANS }, onScan = { screen = Screen.SCANNER }, onLogout = { store.clear(); token = null; serverVersion = null; screen = Screen.LOGIN })
        Screen.DETAILS -> MovieDetailScreen(selected!!, onBack = { screen = Screen.LIBRARY })
        Screen.COLLECTIONS -> CollectionsScreen(api!!, token!!, onBack = { screen = Screen.LIBRARY })
        Screen.LOANS -> LoansScreen(api!!, token!!, onBack = { screen = Screen.LIBRARY })
        Screen.SCANNER -> ScannerScreen(onCode = { code ->
            screen = Screen.BARCODE_RESULT
            scanned = BarcodeResponse("loading", code, null, null, null)
        }, onBack = { screen = Screen.LIBRARY })
        Screen.BARCODE_RESULT -> BarcodeResultScreen(api!!, token!!, scanned?.upc.orEmpty(), onLoaded = { scanned = it }, onBack = { screen = Screen.LIBRARY })
    }
}

private fun normalizeServerUrl(value: String): String {
    var normalized = value.trim()
    if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
        normalized = "http://$normalized"
    }
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

    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.Center) {
            Text("Homebuster", style = MaterialTheme.typography.displaySmall)
            Spacer(Modifier.height(8.dp))
            Text("Your movie library, in your pocket.")
            Text("App v${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)

            if (Build.VERSION.SDK_INT >= 37 && !localNetworkGranted) {
                Spacer(Modifier.height(20.dp))
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("Local network access required", style = MaterialTheme.typography.titleMedium)
                        Text("Android 17 requires permission before Homebuster can connect to a server on your home network.")
                        Spacer(Modifier.height(10.dp))
                        Button(onClick = onRequestLocalNetwork) { Text("Allow local network access") }
                    }
                }
            }

            Spacer(Modifier.height(24.dp))
            OutlinedTextField(server, onServer, label = { Text("Homebuster server URL") }, placeholder = { Text("http://192.168.50.83:8092") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(username, { username = it }, label = { Text("Username") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(password, { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                enabled = !busy && localNetworkGranted && server.isNotBlank() && username.isNotBlank(),
                onClick = {
                    busy = true
                    error = null
                    scope.launch {
                        try {
                            val current = normalizeServerUrl(server)
                            val loginApi = ApiFactory.create(current)
                            val status = loginApi.status()
                            val login = loginApi.login(LoginRequest(username, password))
                            onLoggedIn(current, login.token, status.serverVersion)
                        } catch (e: Exception) {
                            error = friendly(e)
                        } finally {
                            busy = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text(if (busy) "Signing in…" else "Sign in") }
        }
    }
}

private fun friendly(e: Exception): String = when(e){ is HttpException -> "Homebuster returned HTTP ${e.code()}"; else -> e.message ?: "Connection failed" }

@Composable
private fun LibraryScreen(api: HomebusterApi, token: String, serverVersion: String?, onMovie:(Movie)->Unit, onCollections:()->Unit, onLoans:()->Unit, onScan:()->Unit, onLogout:()->Unit) {
    var movies by remember { mutableStateOf<List<Movie>>(emptyList()) }; var query by remember { mutableStateOf("") }; var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(query) { try { movies = api.movies("Bearer $token", query.ifBlank { null }).movies; error=null } catch(e:Exception){ error=friendly(e) } }
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.SpaceBetween){ Column { Text("Homebuster",style=MaterialTheme.typography.headlineMedium); Text("App v${BuildConfig.VERSION_NAME} • Server v${serverVersion ?: "unknown"}", style=MaterialTheme.typography.bodySmall) }; TextButton(onClick=onLogout){Text("Log out")} }
        OutlinedTextField(query,{query=it},label={Text("Search my movies")},modifier=Modifier.fillMaxWidth())
        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.SpaceEvenly){ TextButton(onClick=onCollections){Text("Collections")}; TextButton(onClick=onLoans){Text("Loans")}; Button(onClick=onScan){Text("Scan barcode")}}
        error?.let{Text(it,color=MaterialTheme.colorScheme.error)}
        LazyVerticalGrid(GridCells.Adaptive(140.dp), contentPadding=PaddingValues(top=8.dp), horizontalArrangement=Arrangement.spacedBy(8.dp), verticalArrangement=Arrangement.spacedBy(8.dp)) {
            items(movies, key={it.id}) { m -> Card(Modifier.fillMaxWidth().clickable{onMovie(m)}) { Column { AsyncImage(model=m.posterUrl,contentDescription=m.title,modifier=Modifier.fillMaxWidth().aspectRatio(2f/3f),contentScale=ContentScale.Crop); Text(m.title,Modifier.padding(8.dp),style=MaterialTheme.typography.titleMedium); Text(listOfNotNull(m.year?.toString(),m.format).joinToString(" • "),Modifier.padding(horizontal=8.dp,vertical=0.dp)); Spacer(Modifier.height(8.dp)) } } }
        }
    }
}

@Composable
private fun MovieDetailScreen(movie: Movie, onBack:()->Unit) { LazyColumn(Modifier.fillMaxSize().padding(16.dp)){ item { TextButton(onClick=onBack){Text("‹ Library")}; AsyncImage(model=movie.posterUrl,contentDescription=movie.title,modifier=Modifier.fillMaxWidth().height(420.dp),contentScale=ContentScale.Fit); Text(movie.title,style=MaterialTheme.typography.headlineMedium); Text(listOfNotNull(movie.year?.toString(),movie.format,movie.runtime?.let{"$it min"}).joinToString(" • ")); movie.upc?.let{Text("UPC: $it")}; Spacer(Modifier.height(12.dp)); Text(movie.overview) } } }

@Composable
private fun CollectionsScreen(api:HomebusterApi, token:String, onBack:()->Unit){ var data by remember{mutableStateOf<List<CollectionItem>>(emptyList())}; LaunchedEffect(Unit){runCatching{api.collections("Bearer $token").collections}.onSuccess{data=it}}; Column(Modifier.padding(16.dp)){TextButton(onClick=onBack){Text("‹ Library")};Text("Collections",style=MaterialTheme.typography.headlineMedium);LazyColumn{items(data){c->ListItem(headlineContent={Text(c.name)},supportingContent={Text("${c.movieCount} movies")})}}}}

@Composable
private fun LoansScreen(api:HomebusterApi, token:String, onBack:()->Unit){ var data by remember{mutableStateOf<List<Loan>>(emptyList())}; LaunchedEffect(Unit){runCatching{api.loans("Bearer $token").loans}.onSuccess{data=it}}; Column(Modifier.padding(16.dp)){TextButton(onClick=onBack){Text("‹ Library")};Text("Loans",style=MaterialTheme.typography.headlineMedium);LazyColumn{items(data){l->ListItem(headlineContent={Text(l.title)},supportingContent={Text(if(l.returnedAt==null) "Loaned to ${l.borrower}" else "Returned")})}}}}

@Composable
private fun BarcodeResultScreen(api:HomebusterApi, token:String, upc:String, onLoaded:(BarcodeResponse)->Unit, onBack:()->Unit){ var result by remember(upc){mutableStateOf<BarcodeResponse?>(null)};var error by remember{mutableStateOf<String?>(null)};LaunchedEffect(upc){try{result=api.barcode("Bearer $token",upc);onLoaded(result!!)}catch(e:HttpException){if(e.code()==404) error="Barcode $upc is not in your library and the server could not identify it." else error=friendly(e)}catch(e:Exception){error=friendly(e)}};Column(Modifier.padding(20.dp)){TextButton(onClick=onBack){Text("‹ Library")};Text("Barcode $upc",style=MaterialTheme.typography.headlineMedium);when(val r=result){null->Text(error ?: "Looking up barcode…");else->if(r.status=="owned"&&r.movie!=null){Text("You already own this.",style=MaterialTheme.typography.titleLarge);Text("${r.movie.title} • ${r.movie.format}")}else{Text(r.product?.productTitle ?: "Product found");Text("${r.tmdbResults?.size ?: 0} TMDb matches ready for confirmation")}}}}
