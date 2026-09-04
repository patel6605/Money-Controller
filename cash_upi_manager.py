# streamlit_app.py
import streamlit as st
import io
import zipfile
from datetime import datetime

st.set_page_config(page_title="Cash & UPI Money Manager - Project Export", layout="wide")

st.title("Cash & UPI Money Manager — Project ZIP generator")
st.markdown(
    """
This Streamlit app packages a runnable Android project skeleton (Kotlin + Compose + Room + MVVM)
for the "Cash & UPI Money Manager" you requested. Click the button below to generate a zip
you can import into Android Studio.

Notes:
- After download, open the project in Android Studio (preferably Arctic Fox or newer).
- Ensure Kotlin, AGP and Compose versions match the build.gradle in your environment.
- This is a starter skeleton; add resources, icons, and adjust versions as needed.
"""
)

# Map of filepath -> content
files = {
    "app/build.gradle": """
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    id 'kotlin-kapt'
}

android {
    namespace 'com.example.cashupi'
    compileSdk 34

    defaultConfig {
        applicationId "com.example.cashupi"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }

    buildFeatures {
        compose true
    }

    composeOptions {
        kotlinCompilerExtensionVersion '1.5.4'
    }

    kotlinOptions {
        jvmTarget = '17'
    }

    packagingOptions {
        resources {
            excludes += '/META-INF/{AL2.0,LGPL2.1}'
        }
    }
}

dependencies {
    implementation "androidx.core:core-ktx:1.12.0"
    implementation "androidx.activity:activity-compose:1.8.0"
    implementation "androidx.compose.ui:ui:1.4.8"
    implementation "androidx.compose.material:material:1.4.3"
    implementation "androidx.compose.material3:material3:1.2.0-alpha02"
    implementation "androidx.compose.ui:ui-tooling-preview:1.4.8"
    debugImplementation "androidx.compose.ui:ui-tooling:1.4.8"

    implementation "androidx.navigation:navigation-compose:2.7.0"
    implementation "androidx.lifecycle:lifecycle-runtime-ktx:2.6.2"
    implementation "androidx.lifecycle:lifecycle-viewmodel-compose:2.6.2"

    implementation "androidx.room:room-runtime:2.6.0"
    kapt "androidx.room:room-compiler:2.6.0"
    implementation "androidx.room:room-ktx:2.6.0"

    implementation "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3"
    implementation "org.jetbrains.kotlin:kotlin-stdlib:1.9.10"

    implementation "androidx.compose.material:material-icons-extended:1.4.3"
}
""",
    "settings.gradle": """
rootProject.name = "CashUpi"
include ':app'
""",
    "app/src/main/AndroidManifest.xml": """
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.cashupi">

    <application
        android:allowBackup="true"
        android:label="Cash & UPI Money Manager"
        android:theme="@style/Theme.CashUpi">
        <activity android:name="com.example.cashupi.ui.MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
""",
    # Kotlin sources
    "app/src/main/java/com/example/cashupi/data/TransactionEntity.kt": """
package com.example.cashupi.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "transactions")
data class TransactionEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val date: Long,
    val type: String,
    val amount: Double,
    val wallet: String?,
    val fromWallet: String?,
    val toWallet: String?,
    val person: String?,
    val category: String?,
    val note: String?
)
""",
    "app/src/main/java/com/example/cashupi/data/FDEntity.kt": """
package com.example.cashupi.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "fds")
data class FDEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val startDate: Long,
    val amount: Double,
    val interestRate: Double,
    val maturityDate: Long,
    val bankName: String?,
    val note: String?,
    val status: String
)
""",
    "app/src/main/java/com/example/cashupi/data/PersonPending.kt": """
package com.example.cashupi.data

data class PersonPending(
    val person: String,
    val given: Double,
    val returned: Double,
    val pending: Double
)
""",
    "app/src/main/java/com/example/cashupi/data/AppDao.kt": """
package com.example.cashupi.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface AppDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTransaction(tx: TransactionEntity): Long

    @Delete
    suspend fun deleteTransaction(tx: TransactionEntity)

    @Query("SELECT * FROM transactions ORDER BY date DESC LIMIT :limit")
    fun recentTransactions(limit: Int = 5): Flow<List<TransactionEntity>>

    @Query("SELECT * FROM transactions ORDER BY date DESC")
    fun allTransactions(): Flow<List<TransactionEntity>>

    @Query(\"\"\"
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('Income','Transfer In','Money Returned','FD Matured','FD Interest Payout') THEN amount
                WHEN type IN ('Expense','Transfer Out','Money Given','FD Created') THEN -amount
                ELSE 0
            END
        ), 0.0) FROM transactions WHERE wallet = :wallet
    \"\"\")
    fun walletBalanceFlow(wallet: String): Flow<Double>

    @Query(\"\"\"
        SELECT 
          COALESCE(SUM(
            CASE
              WHEN type IN ('Income','Transfer In','Money Returned','FD Matured','FD Interest Payout') THEN amount
              WHEN type IN ('Expense','Transfer Out','Money Given','FD Created') THEN -amount
              ELSE 0
            END
          ), 0.0) 
        FROM transactions 
        WHERE wallet IN (:wallets)
    \"\"\")
    fun walletsBalanceFlow(wallets: List<String>): Flow<Double>

    @Query(\"\"\"
        SELECT 
            person as person,
            COALESCE(SUM(CASE WHEN type = 'Money Given' THEN amount ELSE 0 END), 0.0) as given,
            COALESCE(SUM(CASE WHEN type = 'Money Returned' THEN amount ELSE 0 END), 0.0) as returned,
            (COALESCE(SUM(CASE WHEN type = 'Money Given' THEN amount ELSE 0 END), 0.0)
             - COALESCE(SUM(CASE WHEN type = 'Money Returned' THEN amount ELSE 0 END), 0.0)) as pending
        FROM transactions
        WHERE person IS NOT NULL AND person != ''
        GROUP BY person
        HAVING (COALESCE(SUM(CASE WHEN type = 'Money Given' THEN amount ELSE 0 END), 0.0)
             - COALESCE(SUM(CASE WHEN type = 'Money Returned' THEN amount ELSE 0 END), 0.0)) > 0
    \"\"\")
    fun pendingPerPerson(): Flow<List<PersonPending>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertFD(fd: FDEntity): Long

    @Update
    suspend fun updateFD(fd: FDEntity)

    @Query("SELECT * FROM fds ORDER BY startDate DESC")
    fun allFDs(): Flow<List<FDEntity>>

    @Query("SELECT COALESCE(SUM(amount), 0.0) FROM fds WHERE status = 'Active'")
    fun activeFDSum(): Flow<Double>

    @Query("SELECT * FROM fds WHERE status = 'Active' ORDER BY maturityDate ASC")
    fun activeFDs(): Flow<List<FDEntity>>

    @Query("SELECT * FROM transactions WHERE id = :id LIMIT 1")
    suspend fun getTransactionById(id: Long): TransactionEntity?
}
""",
    "app/src/main/java/com/example/cashupi/data/AppDatabase.kt": """
package com.example.cashupi.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [TransactionEntity::class, FDEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): AppDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null
        fun getInstance(context: Context): AppDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "cashupi-db"
                ).fallbackToDestructiveMigration().build().also { INSTANCE = it }
            }
    }
}
""",
    "app/src/main/java/com/example/cashupi/repo/CashUpiRepository.kt": """
package com.example.cashupi.repo

import com.example.cashupi.data.*
import kotlinx.coroutines.flow.Flow

class CashUpiRepository(private val dao: AppDao) {

    suspend fun addTransaction(tx: TransactionEntity) = dao.insertTransaction(tx)
    suspend fun deleteTransaction(tx: TransactionEntity) = dao.deleteTransaction(tx)

    fun recentTransactions(limit: Int = 5): Flow<List<TransactionEntity>> = dao.recentTransactions(limit)
    fun allTransactions(): Flow<List<TransactionEntity>> = dao.allTransactions()

    fun walletBalanceFlow(wallet: String): Flow<Double> = dao.walletBalanceFlow(wallet)
    fun walletsBalanceFlow(wallets: List<String>): Flow<Double> = dao.walletsBalanceFlow(wallets)

    fun pendingPerPerson(): Flow<List<PersonPending>> = dao.pendingPerPerson()

    suspend fun addFD(fd: FDEntity) = dao.insertFD(fd)
    suspend fun updateFD(fd: FDEntity) = dao.updateFD(fd)
    fun activeFDSum(): Flow<Double> = dao.activeFDSum()
    fun activeFDs(): Flow<List<FDEntity>> = dao.activeFDs()
    fun allFDs(): Flow<List<FDEntity>> = dao.allFDs()
}
""",
    "app/src/main/java/com/example/cashupi/util/Extensions.kt": """
package com.example.cashupi.util

import java.text.NumberFormat
import java.util.Locale

fun Double.toINR(): String {
    val fmt = NumberFormat.getCurrencyInstance(Locale("en", "IN"))
    return fmt.format(this)
}
""",
    "app/src/main/java/com/example/cashupi/ui/theme/Theme.kt": """
package com.example.cashupi.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF00695C),
    onPrimary = androidx.compose.ui.graphics.Color.White
)

private val DarkColors = darkColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF26A69A),
    onPrimary = androidx.compose.ui.graphics.Color.Black
)

@Composable
fun CashUpiTheme(content: @Composable () -> Unit) {
    val colors = LightColors
    MaterialTheme(
        colorScheme = colors,
        typography = androidx.compose.material3.Typography(),
        content = content
    )
}
""",
    "app/src/main/java/com/example/cashupi/ui/MainActivity.kt": """
package com.example.cashupi.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.cashupi.data.AppDatabase
import com.example.cashupi.repo.CashUpiRepository
import com.example.cashupi.ui.theme.CashUpiTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val db = AppDatabase.getInstance(applicationContext)
        val repository = CashUpiRepository(db.dao())
        setContent {
            CashUpiTheme {
                val vm: MainViewModel = viewModel(factory = MainViewModel.provideFactory(repository))
                CashUpiApp(vm = vm)
            }
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/MainViewModel.kt": """
package com.example.cashupi.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.cashupi.data.FDEntity
import com.example.cashupi.data.TransactionEntity
import com.example.cashupi.data.PersonPending
import com.example.cashupi.repo.CashUpiRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class MainViewModel(private val repo: CashUpiRepository) : ViewModel() {

    val cashBalance: StateFlow<Double> = repo.walletBalanceFlow("Cash")
        .stateIn(viewModelScope, SharingStarted.Lazily, 0.0)

    val upiBalance: StateFlow<Double> = repo.walletBalanceFlow("UPI")
        .stateIn(viewModelScope, SharingStarted.Lazily, 0.0)

    val totalWalletBalance: StateFlow<Double> = repo.walletsBalanceFlow(listOf("Cash", "UPI"))
        .stateIn(viewModelScope, SharingStarted.Lazily, 0.0)

    val activeFDSum = repo.activeFDSum()
        .map { it }
        .stateIn(viewModelScope, SharingStarted.Lazily, 0.0)

    val recentTransactions = repo.recentTransactions(5)
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    val allTransactions = repo.allTransactions()
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    val pendingPerPerson = repo.pendingPerPerson()
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    val activeFDs = repo.activeFDs()
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    fun addTransaction(tx: TransactionEntity) = viewModelScope.launch {
        repo.addTransaction(tx)
    }

    fun deleteTransaction(tx: TransactionEntity) = viewModelScope.launch {
        repo.deleteTransaction(tx)
    }

    fun addFD(fd: FDEntity) = viewModelScope.launch {
        repo.addFD(fd)
    }

    fun updateFD(fd: FDEntity) = viewModelScope.launch {
        repo.updateFD(fd)
    }

    companion object {
        fun provideFactory(repo: CashUpiRepository): ViewModelProvider.Factory {
            return object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return MainViewModel(repo) as T
                }
            }
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/CashUpiApp.kt": """
package com.example.cashupi.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Pending
import androidx.compose.material.icons.filled.Savings
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier

@Composable
fun CashUpiApp(vm: MainViewModel) {
    val navItems = listOf(
        NavItem("home", "Home", Icons.Default.Home),
        NavItem("pending", "Pending", Icons.Default.Pending),
        NavItem("fds", "FDs", Icons.Default.Savings),
        NavItem("history", "History", Icons.Default.History)
    )

    var current by remember { mutableStateOf("home") }

    Scaffold(
        bottomBar = {
            BottomNavigation {
                navItems.forEach { item ->
                    BottomNavigationItem(
                        icon = { Icon(item.icon, contentDescription = item.title) },
                        selected = current == item.route,
                        label = { Text(item.title) },
                        onClick = { current = item.route }
                    )
                }
            }
        }
    ) { innerPadding ->
        when (current) {
            "home" -> com.example.cashupi.ui.home.HomeScreen(vm = vm, modifier = Modifier.padding(innerPadding))
            "pending" -> com.example.cashupi.ui.pending.PendingScreen(vm = vm, modifier = Modifier.padding(innerPadding))
            "fds" -> com.example.cashupi.ui.fd.FDScreen(vm = vm, modifier = Modifier.padding(innerPadding))
            "history" -> com.example.cashupi.ui.history.HistoryScreen(vm = vm, modifier = Modifier.padding(innerPadding))
        }
    }
}

data class NavItem(val route: String, val title: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)
""",
    # For brevity include a minimal HomeScreen, AddTransactionSheet, PendingScreen, FDScreen, HistoryScreen
    "app/src/main/java/com/example/cashupi/ui/home/HomeScreen.kt": """
package com.example.cashupi.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.*
import androidx.compose.material.Card
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.TransactionEntity
import com.example.cashupi.ui.MainViewModel
import com.example.cashupi.util.toINR
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import com.example.cashupi.ui.add.AddTransactionSheet
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(vm: MainViewModel, modifier: Modifier = Modifier) {
    val total by vm.totalWalletBalance.collectAsState()
    val cash by vm.cashBalance.collectAsState()
    val upi by vm.upiBalance.collectAsState()
    val activeFD by vm.activeFDSum.collectAsState()
    val recent by vm.recentTransactions.collectAsState()
    val coroutineScope = rememberCoroutineScope()
    var showAdd by remember { mutableStateOf(false) }

    Box(modifier = modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Card(modifier = Modifier.fillMaxWidth(), elevation = 8.dp) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Available Balance", style = MaterialTheme.typography.h6)
                    Spacer(Modifier.height(8.dp))
                    Text(text = total.toINR(), style = MaterialTheme.typography.h4)
                    Spacer(Modifier.height(12.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text("Cash"); Text(cash.toINR()) }
                        Column { Text("UPI"); Text(upi.toINR()) }
                        Column { Text("Active FDs"); Text(activeFD.toINR()) }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            Text("Recent", style = MaterialTheme.typography.h6)
            Spacer(Modifier.height(8.dp))
            LazyColumn { items(recent) { tx -> TransactionRow(tx = tx) } }
        }

        FloatingActionButton(onClick = { showAdd = true }, modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp)) {
            Icon(Icons.Default.Add, contentDescription = "Add")
        }

        if (showAdd) {
            AddTransactionSheet(onClose = { showAdd = false }, onSave = { tx -> coroutineScope.launch { vm.addTransaction(tx) }; showAdd = false })
        }
    }
}

@Composable
private fun TransactionRow(tx: TransactionEntity) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp), elevation = 2.dp) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(text = tx.type, style = MaterialTheme.typography.subtitle1)
                Text(text = tx.category ?: "", style = MaterialTheme.typography.body2)
            }
            Text(text = tx.amount.toINR())
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/add/AddTransactionSheet.kt": """
package com.example.cashupi.ui.add

import androidx.compose.foundation.layout.*
import androidx.compose.material.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.TransactionEntity
import kotlinx.coroutines.launch

@Composable
fun AddTransactionSheet(onClose: () -> Unit, onSave: (TransactionEntity) -> Unit) {
    val types = listOf("Income", "Expense", "Transfer", "Money Given", "Money Returned", "FD Created", "FD Matured", "FD Interest Payout", "Opening Balance")
    var expanded by remember { mutableStateOf(false) }
    var selectedType by remember { mutableStateOf(types.first()) }
    var amountText by remember { mutableStateOf("") }
    var wallet by remember { mutableStateOf("UPI") }
    var fromWallet by remember { mutableStateOf("") }
    var toWallet by remember { mutableStateOf("") }
    var person by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }

    Surface(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("Add Transaction", style = MaterialTheme.typography.h6)
            Spacer(Modifier.height(8.dp))

            Box {
                OutlinedTextField(value = selectedType, onValueChange = {}, readOnly = true, label = { Text("Type") }, modifier = Modifier.fillMaxWidth())
                DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    types.forEach { t ->
                        DropdownMenuItem(onClick = { selectedType = t; expanded = false }) { Text(t) }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = amountText, onValueChange = { amountText = it }, label = { Text("Amount") }, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = wallet, onValueChange = { wallet = it }, label = { Text("Wallet (Cash/UPI)") }, modifier = Modifier.weight(1f))
                if (selectedType == "Transfer") {
                    OutlinedTextField(value = fromWallet, onValueChange = { fromWallet = it }, label = { Text("From") }, modifier = Modifier.weight(1f))
                    OutlinedTextField(value = toWallet, onValueChange = { toWallet = it }, label = { Text("To") }, modifier = Modifier.weight(1f))
                }
            }

            Spacer(Modifier.height(8.dp))
            if (selectedType == "Money Given" || selectedType == "Money Returned") {
                OutlinedTextField(value = person, onValueChange = { person = it }, label = { Text("Person") }, modifier = Modifier.fillMaxWidth())
            }

            if (selectedType != "Transfer") {
                OutlinedTextField(value = category, onValueChange = { category = it }, label = { Text("Category") }, modifier = Modifier.fillMaxWidth())
            }

            OutlinedTextField(value = note, onValueChange = { note = it }, label = { Text("Note") }, modifier = Modifier.fillMaxWidth())

            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onClose) { Text("Cancel") }
                Spacer(Modifier.width(8.dp))
                Button(onClick = {
                    val amount = amountText.toDoubleOrNull() ?: 0.0
                    val now = System.currentTimeMillis()
                    val tx = TransactionEntity(date = now, type = selectedType, amount = amount, wallet = wallet,
                        fromWallet = if (selectedType == "Transfer") fromWallet else null,
                        toWallet = if (selectedType == "Transfer") toWallet else null,
                        person = if (selectedType == "Money Given" || selectedType == "Money Returned") person else null,
                        category = if (selectedType != "Transfer") category else null, note = note)
                    onSave(tx)
                }) { Text("Save") }
            }
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/pending/PendingScreen.kt": """
package com.example.cashupi.ui.pending

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.Card
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.PersonPending
import com.example.cashupi.ui.MainViewModel
import com.example.cashupi.util.toINR

@Composable
fun PendingScreen(vm: MainViewModel, modifier: Modifier = Modifier) {
    val pending by vm.pendingPerPerson.collectAsState()
    LazyColumn(modifier = modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(pending) { p -> PendingCard(p) }
    }
}

@Composable
fun PendingCard(p: PersonPending) {
    Card(elevation = 4.dp, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(text = p.person)
            Spacer(modifier = Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Column { Text("Given"); Text(p.given.toINR()) }
                Column { Text("Returned"); Text(p.returned.toINR()) }
                Column { Text("Pending"); Text(p.pending.toINR()) }
            }
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/fd/FDScreen.kt": """
package com.example.cashupi.ui.fd

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.Text
import androidx.compose.material.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.FDEntity
import com.example.cashupi.ui.MainViewModel
import com.example.cashupi.util.toINR
import kotlinx.coroutines.launch

@Composable
fun FDScreen(vm: MainViewModel, modifier: Modifier = Modifier) {
    val fds by vm.activeFDs.collectAsState()
    val coroutineScope = rememberCoroutineScope()
    var showNewFd by remember { mutableStateOf(false) }

    Column(modifier = modifier.fillMaxSize().padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Active FDs")
            Button(onClick = { showNewFd = true }) { Text("New FD") }
        }

        Spacer(Modifier.height(8.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(fds) { fd ->
                FDCard(fd = fd, onMature = {
                    coroutineScope.launch {
                        val matured = fd.copy(status = "Matured")
                        vm.updateFD(matured)
                        vm.addTransaction(com.example.cashupi.data.TransactionEntity(
                            date = System.currentTimeMillis(), type = "FD Matured", amount = fd.amount, wallet = "UPI",
                            fromWallet = null, toWallet = null, person = null, category = "FD Matured", note = "Matured: ${fd.bankName}"
                        ))
                    }
                }, onCreditInterest = { interestAmount ->
                    coroutineScope.launch {
                        vm.addTransaction(com.example.cashupi.data.TransactionEntity(
                            date = System.currentTimeMillis(), type = "FD Interest Payout", amount = interestAmount, wallet = "UPI",
                            fromWallet = null, toWallet = null, person = null, category = "FD Interest", note = "Interest for FD ${fd.id}"
                        ))
                    }
                })
            }
        }
    }

    if (showNewFd) {
        NewFDDialog(onDismiss = { showNewFd = false }, onCreate = { fd ->
            coroutineScope.launch {
                vm.addFD(fd)
                vm.addTransaction(com.example.cashupi.data.TransactionEntity(
                    date = System.currentTimeMillis(), type = "FD Created", amount = fd.amount, wallet = "UPI",
                    fromWallet = null, toWallet = null, person = null, category = "FD Created", note = "FD Created in ${fd.bankName}"
                ))
            }
            showNewFd = false
        })
    }
}

@Composable
fun FDCard(fd: FDEntity, onMature: () -> Unit, onCreditInterest: (Double) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text("FD @ ${fd.interestRate}% - ${fd.amount.toINR()}")
            Spacer(Modifier.height(6.dp))
            Text("Bank: ${fd.bankName ?: "Unknown"}")
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { onCreditInterest(fd.amount * fd.interestRate / 100.0 / 12.0) }) { Text("Credit Interest") }
                TextButton(onClick = onMature) { Text("Mature") }
            }
        }
    }
}
""",
    "app/src/main/java/com/example/cashupi/ui/fd/NewFDDialog.kt": """
package com.example.cashupi.ui.fd

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material.AlertDialog
import androidx.compose.material.Button
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.runtime.*
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.FDEntity

@Composable
fun NewFDDialog(onDismiss: () -> Unit, onCreate: (FDEntity) -> Unit) {
    var amountText by remember { mutableStateOf("") }
    var rateText by remember { mutableStateOf("") }
    var maturityDaysText by remember { mutableStateOf("365") }
    var bank by remember { mutableStateOf("") }

    AlertDialog(onDismissRequest = onDismiss, title = { Text("New FD") }, text = {
        Column {
            OutlinedTextField(value = amountText, onValueChange = { amountText = it }, label = { Text("Amount") })
            OutlinedTextField(value = rateText, onValueChange = { rateText = it }, label = { Text("Rate (%)") })
            OutlinedTextField(value = maturityDaysText, onValueChange = { maturityDaysText = it }, label = { Text("Maturity days") })
            OutlinedTextField(value = bank, onValueChange = { bank = it }, label = { Text("Bank") })
            Spacer(modifier = androidx.compose.ui.Modifier.height(8.dp))
        }
    }, confirmButton = {
        Button(onClick = {
            val amount = amountText.toDoubleOrNull() ?: 0.0
            val rate = rateText.toDoubleOrNull() ?: 0.0
            val days = maturityDaysText.toLongOrNull() ?: 365L
            val start = System.currentTimeMillis()
            val maturity = start + days * 24L * 60L * 60L * 1000L
            val fd = FDEntity(startDate = start, amount = amount, interestRate = rate, maturityDate = maturity, bankName = bank, note = null, status = "Active")
            onCreate(fd)
        }) { Text("Create") }
    }, dismissButton = { Button(onClick = onDismiss) { Text("Cancel") } })
}
""",
    "app/src/main/java/com/example/cashupi/ui/history/HistoryScreen.kt": """
package com.example.cashupi.ui.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.cashupi.data.TransactionEntity
import com.example.cashupi.ui.MainViewModel
import kotlinx.coroutines.launch
import com.example.cashupi.util.toINR

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun HistoryScreen(vm: MainViewModel, modifier: Modifier = Modifier) {
    val all by vm.allTransactions.collectAsState()
    val coroutineScope = rememberCoroutineScope()

    LazyColumn(modifier = modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(all, key = { it.id }) { tx ->
            val dismissState = rememberDismissState()
            if (dismissState.isDismissed(DismissDirection.EndToStart)) {
                LaunchedEffect(tx.id) { vm.deleteTransaction(tx) }
            }
            SwipeToDismiss(state = dismissState, background = {
                Box(modifier = Modifier.fillMaxSize().padding(8.dp), contentAlignment = androidx.compose.ui.Alignment.CenterEnd) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete")
                }
            }, dismissContent = {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(modifier = Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text(tx.type); Text(tx.category ?: "") }
                        Text(tx.amount.toINR())
                    }
                }
            }, directions = setOf(DismissDirection.EndToStart))
        }
    }
}
"""
}

def create_zip_bytes(file_map):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        # Add a README
        readme = f"""Cash & UPI Money Manager - exported {datetime.utcnow().isoformat()}Z

This ZIP contains a minimal Android app skeleton (Compose + Room + MVVM).
Open in Android Studio, sync Gradle, enable kapt, and run on an emulator/device.
"""
        z.writestr("README.txt", readme)
        # Write files
        for path, content in file_map.items():
            z.writestr(path, content.lstrip("\n"))
    buf.seek(0)
    return buf

st.markdown("### Files included (skeleton)")
st.write(list(files.keys())[:10])
if len(files) > 10:
    st.write(f"... (+{len(files)-10} more files)")

zip_buf = create_zip_bytes(files)
b = zip_buf.read()

st.download_button(
    label="Generate & download project ZIP",
    data=b,
    file_name="cashupi_project.zip",
    mime="application/zip"
)

st.markdown("### After download: quick steps")
st.markdown("""
1. Unzip and open the project in Android Studio.
2. Let Gradle sync. If kapt errors appear, ensure `kotlin-kapt` plugin is applied (it is in the included build.gradle).
3. If Room annotation processing complains, run Build → Clean Project, then Rebuild.
4. Run the app on an emulator or device.
""")

st.markdown("If you want, I can also: \n- Update versions in build.gradle to match a specific Compose/AGP toolchain\n- Add sample seed data insertion code\n- Convert the UI sheet to Material3 ModalBottomSheet\nTell me which.")
