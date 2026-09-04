import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CashUpiManagerApp());
}

// =========================================================================
// DATABASE HELPER (SQFLITE)
// =========================================================================
class DatabaseHelper {
  static final DatabaseHelper instance = DatabaseHelper._init();
  static Database? _database;

  DatabaseHelper._init();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDB('cash_upi_manager.db');
    return _database!;
  }

  Future<Database> _initDB(String filePath) async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, filePath);

    return await openDatabase(
      path,
      version: 1,
      onCreate: _createDB,
    );
  }

  Future _createDB(Database db, int version) async {
    await db.execute('''
      CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_date TEXT NOT NULL,
        tx_type TEXT NOT NULL,
        amount REAL NOT NULL,
        wallet TEXT,
        from_wallet TEXT,
        to_wallet TEXT,
        person TEXT,
        category TEXT,
        note TEXT,
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE fds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT NOT NULL,
        amount REAL NOT NULL,
        interest_rate REAL NOT NULL,
        maturity_date TEXT,
        bank_name TEXT,
        note TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        created_at TEXT NOT NULL
      )
    ''');
  }

  Future<int> insertTransaction(Map<String, dynamic> row) async {
    final db = await instance.database;
    return await db.insert('transactions', row);
  }

  Future<List<Map<String, dynamic>>> queryTransactions() async {
    final db = await instance.database;
    return await db.query('transactions', orderBy: 'tx_date DESC, id DESC');
  }

  Future<int> deleteTransaction(int id) async {
    final db = await instance.database;
    return await db.delete('transactions', where: 'id = ?', whereArgs: [id]);
  }

  Future<int> insertFd(Map<String, dynamic> row) async {
    final db = await instance.database;
    return await db.insert('fds', row);
  }

  Future<List<Map<String, dynamic>>> queryFds({String status = 'Active'}) async {
    final db = await instance.database;
    return await db.query('fds', where: 'status = ?', whereArgs: [status], orderBy: 'start_date DESC');
  }

  Future<int> updateFdStatus(int id, String status) async {
    final db = await instance.database;
    return await db.update('fds', {'status': status}, where: 'id = ?', whereArgs: [id]);
  }
}

// =========================================================================
// APP ROOT & THEME
// =========================================================================
class CashUpiManagerApp extends StatelessWidget {
  const CashUpiManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Cash & UPI Manager',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.system,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        primaryColor: const Color(0xFF2563EB),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2563EB),
          brightness: Brightness.light,
        ),
        cardTheme: CardThemeData(
          color: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: Color(0xFFCBD5E1), width: 1),
          ),
        ),
      ),
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0B1020),
        primaryColor: const Color(0xFF3B82F6),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3B82F6),
          brightness: Brightness.dark,
        ),
        cardTheme: CardThemeData(
          color: const Color(0xFF141C2E),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: Color(0x408091B4), width: 1),
          ),
        ),
      ),
      home: const MainNavigationScreen(),
    );
  }
}

// =========================================================================
// MAIN NAVIGATION & TABS
// =========================================================================
class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    const DashboardTab(),
    const AddTransactionTab(),
    const PendingMoneyTab(),
    const FdTab(),
    const HistoryTab(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF2563EB),
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home_rounded), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.add_circle_outline_rounded), label: 'Add'),
          BottomNavigationBarItem(icon: Icon(Icons.hourglass_top_rounded), label: 'Pending'),
          BottomNavigationBarItem(icon: Icon(Icons.account_balance_rounded), label: 'FDs'),
          BottomNavigationBarItem(icon: Icon(Icons.history_rounded), label: 'History'),
        ],
      ),
    );
  }
}

// =========================================================================
// 1. DASHBOARD TAB
// =========================================================================
class DashboardTab extends StatefulWidget {
  const DashboardTab({super.key});

  @override
  State<DashboardTab> createState() => _DashboardTabState();
}

class _DashboardTabState extends State<DashboardTab> {
  double cashBalance = 0;
  double upiBalance = 0;
  double pendingTotal = 0;
  double activeFdTotal = 0;
  List<Map<String, dynamic>> recentTransactions = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final txs = await DatabaseHelper.instance.queryTransactions();
    final fds = await DatabaseHelper.instance.queryFds(status: 'Active');

    double cash = 0;
    double upi = 0;
    Map<String, double> pendingMap = {};

    for (var tx in txs) {
      final type = tx['tx_type'];
      final amount = tx['amount'] as double;
      final wallet = tx['wallet'];
      final from = tx['from_wallet'];
      final to = tx['to_wallet'];
      final person = tx['person'];

      if (wallet == 'Cash') {
        if (type == 'Income' || type == 'Opening Balance' || type == 'Money Returned') cash += amount;
        if (type == 'Expense' || type == 'Money Given') cash -= amount;
      } else if (wallet == 'UPI') {
        if (type == 'Income' || type == 'Opening Balance' || type == 'Money Returned' || type == 'FD Matured' || type == 'FD Interest Payout') upi += amount;
        if (type == 'Expense' || type == 'Money Given' || type == 'FD Created') upi -= amount;
      }

      if (type == 'Transfer') {
        if (from == 'Cash') cash -= amount;
        if (from == 'UPI') upi -= amount;
        if (to == 'Cash') cash += amount;
        if (to == 'UPI') upi += amount;
      }

      if (person != null && person.toString().trim().isNotEmpty) {
        pendingMap.putIfAbsent(person, () => 0);
        if (type == 'Money Given') pendingMap[person] = pendingMap[person]! + amount;
        if (type == 'Money Returned') pendingMap[person] = pendingMap[person]! - amount;
      }
    }

    double totalPending = 0;
    pendingMap.forEach((_, val) {
      if (val > 0) totalPending += val;
    });

    double fdTotal = 0;
    for (var fd in fds) {
      fdTotal += fd['amount'] as double;
    }

    setState(() {
      cashBalance = cash;
      upiBalance = upi;
      pendingTotal = totalPending;
      activeFdTotal = fdTotal;
      recentTransactions = txs.take(10).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final combined = cashBalance + upiBalance;

    return Scaffold(
      appBar: AppBar(
        title: const Text('💰 Cash & UPI Manager', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: _metricCard('💵 Cash Balance', cashBalance, context)),
                  const SizedBox(width: 12),
                  Expanded(child: _metricCard('📱 UPI Balance', upiBalance, context)),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: _metricCard('💰 Combined Total', combined, context)),
                  const SizedBox(width: 12),
                  Expanded(child: _metricCard('⏳ Pending Money', pendingTotal, context)),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF2563EB), Color(0xFF1E40AF)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('🏦 Active Fixed Deposits', style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    Text('₹${activeFdTotal.toStringAsFixed(2)}', style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    const Text('Monthly interest routes automatically to UPI', style: TextStyle(color: Colors.white60, fontSize: 12)),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              const Text('Recent Transactions', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              recentTransactions.isEmpty
                  ? const Padding(padding: EdgeInsets.all(30), child: Center(child: Text('No transactions yet.')))
                  : ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: recentTransactions.length,
                      itemBuilder: (context, index) {
                        final tx = recentTransactions[index];
                        final isPositive = ['Income', 'Opening Balance', 'Money Returned', 'FD Matured', 'FD Interest Payout'].contains(tx['tx_type']);
                        return Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isDark ? const Color(0xFF141C2E) : Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: isDark ? const Color(0x408091B4) : const Color(0xFFCBD5E1), width: 1),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(10),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFF2563EB).withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: const Icon(Icons.receipt_long_rounded, color: Color(0xFF2563EB), size: 20),
                                  ),
                                  const SizedBox(width: 12),
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(tx['tx_type'], style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                                      const SizedBox(height: 2),
                                      Text('${tx['wallet'] ?? tx['from_wallet'] ?? ''} • ${tx['tx_date']}', style: TextStyle(color: Colors.grey, fontSize: 12)),
                                    ],
                                  ),
                                ],
                              ),
                              Text(
                                '${isPositive ? "+" : "-"}₹${(tx['amount'] as double).toStringAsFixed(2)}',
                                style: TextStyle(color: isPositive ? Colors.green : Colors.redAccent, fontWeight: FontWeight.bold, fontSize: 15),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _metricCard(String title, double amount, BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text('₹${amount.toStringAsFixed(2)}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}

// =========================================================================
// 2. ADD TRANSACTION TAB
// =========================================================================
class AddTransactionTab extends StatefulWidget {
  const AddTransactionTab({super.key});

  @override
  State<AddTransactionTab> createState() => _AddTransactionTabState();
}

class _AddTransactionTabState extends State<AddTransactionTab> {
  String txType = 'Income';
  final _amountController = TextEditingController();
  final _personController = TextEditingController();
  final _categoryController = TextEditingController();
  final _noteController = TextEditingController();
  String selectedWallet = 'UPI';
  String fromWallet = 'Cash';
  String toWallet = 'UPI';
  DateTime selectedDate = DateTime.now();

  void _saveTransaction() async {
    final amount = double.tryParse(_amountController.text) ?? 0;
    if (amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please enter a valid amount')));
      return;
    }

    await DatabaseHelper.instance.insertTransaction({
      'tx_date': selectedDate.toIso8601String().split('T')[0],
      'tx_type': txType,
      'amount': amount,
      'wallet': txType == 'Transfer' ? null : selectedWallet,
      'from_wallet': txType == 'Transfer' ? fromWallet : null,
      'to_wallet': txType == 'Transfer' ? toWallet : null,
      'person': _personController.text.trim(),
      'category': _categoryController.text.trim(),
      'note': _noteController.text.trim(),
      'created_at': DateTime.now().toString(),
    });

    _amountController.clear();
    _personController.clear();
    _categoryController.clear();
    _noteController.clear();

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Saved $txType successfully!')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('➕ Add Transaction')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            DropdownButtonFormField<String>(
              value: txType,
              decoration: InputDecoration(labelText: 'Transaction Type', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
              items: ['Opening Balance', 'Income', 'Expense', 'Transfer', 'Money Given', 'Money Returned']
                  .map((type) => DropdownMenuItem(value: type, child: Text(type)))
                  .toList(),
              onChanged: (val) => setState(() => txType = val!),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _amountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: 'Amount (₹)', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
            ),
            const SizedBox(height: 16),
            if (txType == 'Transfer') ...[
              Row(
                children: [
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      value: fromWallet,
                      decoration: InputDecoration(labelText: 'From Wallet', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                      items: ['Cash', 'UPI'].map((w) => DropdownMenuItem(value: w, child: Text(w))).toList(),
                      onChanged: (val) => setState(() => fromWallet = val!),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      value: toWallet,
                      decoration: InputDecoration(labelText: 'To Wallet', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                      items: ['Cash', 'UPI'].map((w) => DropdownMenuItem(value: w, child: Text(w))).toList(),
                      onChanged: (val) => setState(() => toWallet = val!),
                    ),
                  ),
                ],
              ),
            ] else ...[
              DropdownButtonFormField<String>(
                value: selectedWallet,
                decoration: InputDecoration(labelText: 'Wallet', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                items: ['Cash', 'UPI'].map((w) => DropdownMenuItem(value: w, child: Text(w))).toList(),
                onChanged: (val) => setState(() => selectedWallet = val!),
              ),
            ],
            if (txType == 'Money Given' || txType == 'Money Returned') ...[
              const SizedBox(height: 16),
              TextField(
                controller: _personController,
                decoration: InputDecoration(labelText: 'Person Name', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
              ),
            ],
            if (txType == 'Income' || txType == 'Expense') ...[
              const SizedBox(height: 16),
              TextField(
                controller: _categoryController,
                decoration: InputDecoration(labelText: 'Category (e.g., Food, Salary)', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
              ),
            ],
            const SizedBox(height: 16),
            TextField(
              controller: _noteController,
              decoration: InputDecoration(labelText: 'Notes / Details', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF2563EB),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _saveTransaction,
                child: const Text('💾 Save Transaction', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// =========================================================================
// 3. PENDING MONEY TAB
// =========================================================================
class PendingMoneyTab extends StatefulWidget {
  const PendingMoneyTab({super.key});

  @override
  State<PendingMoneyTab> createState() => _PendingMoneyTabState();
}

class _PendingMoneyTabState extends State<PendingMoneyTab> {
  Map<String, double> pendingDetails = {};

  @override
  void initState() {
    super.initState();
    _loadPending();
  }

  Future<void> _loadPending() async {
    final txs = await DatabaseHelper.instance.queryTransactions();
    Map<String, double> map = {};
    for (var tx in txs) {
      final person = tx['person'];
      final type = tx['tx_type'];
      final amount = tx['amount'] as double;
      if (person != null && person.toString().trim().isNotEmpty) {
        map.putIfAbsent(person, () => 0);
        if (type == 'Money Given') map[person] = map[person]! + amount;
        if (type == 'Money Returned') map[person] = map[person]! - amount;
      }
    }
    setState(() {
      pendingDetails = Map.fromEntries(map.entries.where((e) => e.value > 0));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('⏳ Pending Money Tracker')),
      body: pendingDetails.isEmpty
          ? const Center(child: Text('No pending money records.'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: pendingDetails.length,
              itemBuilder: (context, index) {
                final person = pendingDetails.keys.elementAt(index);
                final amount = pendingDetails.values.elementAt(index);
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    title: Text(person, style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: const Text('Pending Outflow'),
                    trailing: Text('₹${amount.toStringAsFixed(2)}', style: const TextStyle(color: Colors.orange, fontWeight: FontWeight.bold, fontSize: 16)),
                  ),
                );
              },
            ),
    );
  }
}

// =========================================================================
// 4. FIXED DEPOSITS TAB (WITH MONTHLY INTEREST TO UPI)
// =========================================================================
class FdTab extends StatefulWidget {
  const FdTab({super.key});

  @override
  State<FdTab> createState() => _FdTabState();
}

class _FdTabState extends State<FdTab> {
  List<Map<String, dynamic>> activeFds = [];
  final _amountController = TextEditingController();
  final _rateController = TextEditingController(text: '6.5');
  final _bankController = TextEditingController();
  final _noteController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadFds();
  }

  Future<void> _loadFds() async {
    final fds = await DatabaseHelper.instance.queryFds(status: 'Active');
    setState(() => activeFds = fds);
  }

  void _createFd() async {
    final amount = double.tryParse(_amountController.text) ?? 0;
    final rate = double.tryParse(_rateController.text) ?? 0;
    if (amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter valid principal amount')));
      return;
    }

    await DatabaseHelper.instance.insertFd({
      'start_date': DateTime.now().toIso8601String().split('T')[0],
      'amount': amount,
      'interest_rate': rate,
      'maturity_date': DateTime.now().add(const Duration(days: 365)).toIso8601String().split('T')[0],
      'bank_name': _bankController.text.trim(),
      'note': _noteController.text.trim(),
      'status': 'Active',
      'created_at': DateTime.now().toString(),
    });

    await DatabaseHelper.instance.insertTransaction({
      'tx_date': DateTime.now().toIso8601String().split('T')[0],
      'tx_type': 'FD Created',
      'amount': amount,
      'wallet': 'UPI',
      'note': 'FD created from UPI wallet',
      'created_at': DateTime.now().toString(),
    });

    _amountController.clear();
    _bankController.clear();
    _noteController.clear();
    _loadFds();
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('FD created successfully!')));
  }

  void _recordInterest(int fdId, double principal, double rate) async {
    final monthlyInterest = roundVal((principal * (rate / 100)) / 12);
    await DatabaseHelper.instance.insertTransaction({
      'tx_date': DateTime.now().toIso8601String().split('T')[0],
      'tx_type': 'FD Interest Payout',
      'amount': monthlyInterest,
      'wallet': 'UPI',
      'note': 'FD #$fdId monthly interest credited to UPI',
      'created_at': DateTime.now().toString(),
    });
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Credited ₹$monthlyInterest interest to UPI!')));
  }

  double roundVal(double val) => double.parse(val.toStringAsFixed(2));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('🏦 Fixed Deposits & Interest')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Active Fixed Deposits', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            activeFds.isEmpty
                ? const Text('No active FDs.')
                : ListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: activeFds.length,
                    itemBuilder: (context, index) {
                      final fd = activeFds[index];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${fd['bank_name'] ?? 'Bank'} • ₹${fd['amount']}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                              const SizedBox(height: 4),
                              Text('Interest Rate: ${fd['interest_rate']}% p.a.', style: const TextStyle(color: Colors.grey)),
                              const SizedBox(height: 12),
                              ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
                                icon: const Icon(Icons.download_rounded, size: 16),
                                label: const Text('Record Monthly Interest to UPI'),
                                onPressed: () => _recordInterest(fd['id'], fd['amount'], fd['interest_rate']),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
            const Divider(height: 40),
            const Text('➕ Create FD from UPI', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(controller: _amountController, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Principal Amount (₹)', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: _rateController, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Annual Interest %', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: _bankController, decoration: const InputDecoration(labelText: 'Bank Name', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: _noteController, decoration: const InputDecoration(labelText: 'Notes', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2563EB), foregroundColor: Colors.white),
                onPressed: _createFd,
                child: const Text('Create FD', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// =========================================================================
// 5. HISTORY TAB & DELETION
// =========================================================================
class HistoryTab extends StatefulWidget {
  const HistoryTab({super.key});

  @override
  State<HistoryTab> createState() => _HistoryTabState();
}

class _HistoryTabState extends State<HistoryTab> {
  List<Map<String, dynamic>> transactions = [];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final txs = await DatabaseHelper.instance.queryTransactions();
    setState(() => transactions = txs);
  }

  void _deleteTx(int id) async {
    await DatabaseHelper.instance.deleteTransaction(id);
    _loadHistory();
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Transaction deleted.')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('📋 Complete History')),
      body: transactions.isEmpty
          ? const Center(child: Text('No transaction history.'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: transactions.length,
              itemBuilder: (context, index) {
                final tx = transactions[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    title: Text(tx['tx_type'], style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text('₹${tx['amount']} • ${tx['tx_date']}\n${tx['note'] ?? ''}'),
                    isThreeLine: true,
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.red),
                      onPressed: () => _deleteTx(tx['id']),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
