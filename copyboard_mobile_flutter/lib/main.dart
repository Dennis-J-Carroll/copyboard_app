import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vibration/vibration.dart';
import 'dart:convert';

void main() {
  runApp(const CopyBoardApp());
}

class CopyBoardApp extends StatelessWidget {
  const CopyBoardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CopyBoard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: const Color(0xFFe94560),
        scaffoldBackgroundColor: const Color(0xFF1a1a2e),
        colorScheme: ColorScheme.dark(
          primary: const Color(0xFFe94560),
          secondary: const Color(0xFF0f3460),
          surface: const Color(0xFF16213e),
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF16213e),
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: Color(0xFF0f3460)),
          ),
        ),
      ),
      home: const CopyBoardHome(),
    );
  }
}

class CopyBoardHome extends StatefulWidget {
  const CopyBoardHome({super.key});

  @override
  State<CopyBoardHome> createState() => _CopyBoardHomeState();
}

class _CopyBoardHomeState extends State<CopyBoardHome> {
  static const String storageKey = 'copyboard_items';
  static const String maxItemsKey = 'copyboard_max_items';
  static const int defaultMaxItems = 10;

  List<String> clipboardItems = [];
  int maxItems = defaultMaxItems;
  int selectedIndex = -1;
  bool isDragging = false;
  bool showSettings = false;
  double dragDistance = 0.0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  // Load clipboard items and settings
  Future<void> _loadData() async {
    final prefs = await SharedPreferences.getInstance();

    // Load items
    final itemsJson = prefs.getString(storageKey);
    if (itemsJson != null) {
      final List<dynamic> decoded = json.decode(itemsJson);
      setState(() {
        clipboardItems = decoded.cast<String>();
      });
    }

    // Load max items
    final savedMaxItems = prefs.getInt(maxItemsKey);
    if (savedMaxItems != null) {
      setState(() {
        maxItems = savedMaxItems;
      });
    }
  }

  // Save clipboard items
  Future<void> _saveItems() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(storageKey, json.encode(clipboardItems));
  }

  // Save max items setting
  Future<void> _saveMaxItems(int value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(maxItemsKey, value);
    setState(() {
      maxItems = value;
      // Trim items if necessary
      if (clipboardItems.length > maxItems) {
        clipboardItems = clipboardItems.sublist(0, maxItems);
        _saveItems();
      }
    });
  }

  // Add item from system clipboard
  Future<void> _addFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final text = data?.text?.trim();

    if (text == null || text.isEmpty) {
      _showSnackBar('Clipboard is empty!', isError: true);
      return;
    }

    // Don't add duplicate at top
    if (clipboardItems.isNotEmpty && clipboardItems[0] == text) {
      _showSnackBar('Already at the top!', isError: true);
      return;
    }

    setState(() {
      clipboardItems.insert(0, text);
      if (clipboardItems.length > maxItems) {
        clipboardItems = clipboardItems.sublist(0, maxItems);
      }
    });

    await _saveItems();
    _vibrate(10);
    _showSnackBar('Added to board (${clipboardItems.length}/$maxItems)');
  }

  // Copy item to clipboard
  Future<void> _copyToClipboard(int index) async {
    if (index < 0 || index >= clipboardItems.length) return;

    await Clipboard.setData(ClipboardData(text: clipboardItems[index]));
    _vibrate(15);
    _showSnackBar('📋 Item ${index + 1} copied to clipboard!');
  }

  // Remove item
  Future<void> _removeItem(int index) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Item'),
        content: Text('Remove item ${index + 1}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (result == true) {
      setState(() {
        clipboardItems.removeAt(index);
      });
      await _saveItems();
      _vibrate(20);
    }
  }

  // Clear all items
  Future<void> _clearAll() async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear All'),
        content: const Text('Remove all clipboard items?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (result == true) {
      setState(() {
        clipboardItems.clear();
      });
      await _saveItems();
      _vibrate(30);
    }
  }

  // Vibrate device
  void _vibrate(int duration) async {
    if (await Vibration.hasVibrator() ?? false) {
      Vibration.vibrate(duration: duration);
    }
  }

  // Show snackbar
  void _showSnackBar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red[700] : const Color(0xFFe94560),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  // Calculate selected index from drag distance
  int _calculateSelectedIndex(double distance) {
    const itemHeight = 80.0;
    final index = (distance.abs() / itemHeight).floor();
    return index.clamp(0, clipboardItems.length - 1);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Text('📋 ', style: TextStyle(fontSize: 24)),
            Text('CopyBoard', style: TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        backgroundColor: const Color(0xFF16213e),
        elevation: 0,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Center(
              child: Text(
                '${clipboardItems.length}/$maxItems',
                style: const TextStyle(color: Color(0xFF8b98a8), fontSize: 14),
              ),
            ),
          ),
          IconButton(
            icon: const Text('⚙️', style: TextStyle(fontSize: 24)),
            onPressed: () {
              setState(() {
                showSettings = !showSettings;
              });
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Settings Panel
          if (showSettings) _buildSettingsPanel(),

          // Instructions
          Container(
            padding: const EdgeInsets.all(15),
            color: const Color(0xFF0f3460),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '👆 Tap item to copy • Long press to remove',
                  style: TextStyle(color: Color(0xFF8b98a8), fontSize: 12),
                ),
                SizedBox(height: 3),
                Text(
                  '👇 Hold & drag down first item to select while pasting',
                  style: TextStyle(color: Color(0xFF8b98a8), fontSize: 12),
                ),
              ],
            ),
          ),

          // Action Buttons
          Padding(
            padding: const EdgeInsets.all(15),
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _addFromClipboard,
                    icon: const Text('➕'),
                    label: const Text('Add from Clipboard'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFe94560),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 15),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                ),
                if (clipboardItems.isNotEmpty) ...[
                  const SizedBox(width: 10),
                  ElevatedButton.icon(
                    onPressed: _clearAll,
                    icon: const Text('🗑️'),
                    label: const Text('Clear'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF533483),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        vertical: 15,
                        horizontal: 15,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),

          // Clipboard Items List
          Expanded(
            child: clipboardItems.isEmpty
                ? _buildEmptyState()
                : _buildItemsList(),
          ),

          // Drag Indicator
          if (isDragging) _buildDragIndicator(),
        ],
      ),
    );
  }

  Widget _buildSettingsPanel() {
    final options = [5, 6, 7, 8, 9, 10, 12, 15, 20];

    return Container(
      padding: const EdgeInsets.all(15),
      color: const Color(0xFF16213e),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Max Items',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: options.map((num) {
              final isSelected = maxItems == num;
              return GestureDetector(
                onTap: () => _saveMaxItems(num),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? const Color(0xFFe94560)
                        : const Color(0xFF0f3460),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isSelected
                          ? const Color(0xFFe94560)
                          : const Color(0xFF1a5490),
                    ),
                  ),
                  child: Text(
                    num.toString(),
                    style: TextStyle(
                      color: isSelected ? Colors.white : const Color(0xFF8b98a8),
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('📋', style: TextStyle(fontSize: 64)),
            const SizedBox(height: 20),
            Text(
              'No clipboard items yet',
              style: TextStyle(
                color: const Color(0xFF8b98a8),
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Copy something, then tap "Add from Clipboard"',
              style: TextStyle(
                color: const Color(0xFF5a6a7a),
                fontSize: 14,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildItemsList() {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 8),
      itemCount: clipboardItems.length,
      itemBuilder: (context, index) {
        final isSelected = isDragging && selectedIndex == index;
        final item = clipboardItems[index];

        return GestureDetector(
          onTap: () => _copyToClipboard(index),
          onLongPress: () => _removeItem(index),
          onVerticalDragStart: index == 0
              ? (details) {
                  setState(() {
                    isDragging = true;
                    selectedIndex = 0;
                    dragDistance = 0;
                  });
                  _vibrate(10);
                }
              : null,
          onVerticalDragUpdate: index == 0
              ? (details) {
                  setState(() {
                    dragDistance += details.delta.dy;
                    final newIndex = _calculateSelectedIndex(dragDistance);
                    if (newIndex != selectedIndex) {
                      selectedIndex = newIndex;
                      _vibrate(5);
                    }
                  });
                }
              : null,
          onVerticalDragEnd: index == 0
              ? (details) {
                  if (selectedIndex >= 0 && selectedIndex < clipboardItems.length) {
                    _copyToClipboard(selectedIndex);
                  }
                  setState(() {
                    isDragging = false;
                    selectedIndex = -1;
                    dragDistance = 0;
                  });
                }
              : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.only(bottom: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF16213e),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected
                    ? const Color(0xFFe94560)
                    : const Color(0xFF0f3460),
                width: isSelected ? 2 : 1,
              ),
            ),
            transform: Matrix4.identity()
              ..scale(isSelected ? 1.02 : 1.0),
            child: Padding(
              padding: const EdgeInsets.all(15),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0xFFe94560),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${index + 1}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        index == 0 ? '📌 Most Recent' : 'Item ${index + 1}',
                        style: const TextStyle(
                          color: Color(0xFF8b98a8),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    item,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildDragIndicator() {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: Container(
        margin: const EdgeInsets.all(20),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: const Color(0xFFe94560),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          '📍 Release to paste item ${selectedIndex + 1}',
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}
