import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:super_drag_and_drop/super_drag_and_drop.dart';

const ink = Color(0xFF141512);
const panel = Color(0xFF1B1D19);
const panelRaised = Color(0xFF242620);
const panelSoft = Color(0xFF2C2E27);
const line = Color(0xFF3C3E35);
const paper = Color(0xFFF2EEDF);
const textDim = Color(0xFFA6A394);
const textFaint = Color(0xFF6F7167);
const orange = Color(0xFFFF6B35);
const brass = Color(0xFFC7A86B);
const mint = Color(0xFF8FB996);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final board = await BoardStore.load();
  runApp(CopyBoardApp(board: board));
}

class BoardStore extends ChangeNotifier {
  BoardStore._(this._preferences, this._items);

  static const chamberCount = 10;
  static const storageKey = 'copyboard_rounds_v2';

  final SharedPreferences _preferences;
  List<String> _items;

  List<String> get items => List.unmodifiable(_items);
  int get loadedCount => _items.length;

  static Future<BoardStore> load() async {
    final preferences = await SharedPreferences.getInstance();
    final encoded = preferences.getString(storageKey);
    if (encoded == null) {
      return BoardStore._(preferences, []);
    }
    try {
      final decoded = jsonDecode(encoded) as List<dynamic>;
      final items = decoded.whereType<String>().take(chamberCount).toList();
      return BoardStore._(preferences, items);
    } on FormatException {
      return BoardStore._(preferences, []);
    }
  }

  String? itemAt(int index) {
    if (index < 0 || index >= _items.length) return null;
    return _items[index];
  }

  Future<bool> captureClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final content = data?.text;
    if (content == null || content.trim().isEmpty) return false;
    await loadRound(content);
    return true;
  }

  Future<void> loadRound(String content) async {
    if (_items.isNotEmpty && _items.first == content) return;
    _items = [content, ..._items].take(chamberCount).toList();
    await _save();
    notifyListeners();
  }

  Future<bool> copyRound(int index) async {
    final content = itemAt(index);
    if (content == null) return false;
    await Clipboard.setData(ClipboardData(text: content));
    return true;
  }

  Future<void> eject(int index) async {
    if (index < 0 || index >= _items.length) return;
    _items = [..._items]..removeAt(index);
    await _save();
    notifyListeners();
  }

  Future<void> clear() async {
    _items = [];
    await _save();
    notifyListeners();
  }

  Future<void> _save() async {
    await _preferences.setString(storageKey, jsonEncode(_items));
  }
}

class CopyBoardApp extends StatelessWidget {
  const CopyBoardApp({super.key, required this.board});

  final BoardStore board;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CopyBoard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: ink,
        colorScheme: const ColorScheme.dark(
          primary: orange,
          secondary: brass,
          surface: panel,
          error: Color(0xFFE56B6F),
        ),
        fontFamily: 'Roboto',
        useMaterial3: true,
      ),
      home: RevolverHome(board: board),
    );
  }
}

class RevolverHome extends StatefulWidget {
  const RevolverHome({super.key, required this.board});

  final BoardStore board;

  @override
  State<RevolverHome> createState() => _RevolverHomeState();
}

class _RevolverHomeState extends State<RevolverHome> {
  int selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    widget.board.addListener(_boardChanged);
  }

  @override
  void dispose() {
    widget.board.removeListener(_boardChanged);
    super.dispose();
  }

  void _boardChanged() {
    if (!mounted) return;
    setState(() {
      selectedIndex = math.max(
        0,
        math.min(selectedIndex, BoardStore.chamberCount - 1),
      );
    });
  }

  Future<void> _capture() async {
    final captured = await widget.board.captureClipboard();
    if (!mounted) return;
    if (captured) {
      setState(() => selectedIndex = 0);
      HapticFeedback.mediumImpact();
      _message('Loaded clipboard into chamber 01');
    } else {
      _message('The clipboard has no text', error: true);
    }
  }

  Future<void> _copy(int index) async {
    setState(() => selectedIndex = index);
    if (await widget.board.copyRound(index) && mounted) {
      HapticFeedback.selectionClick();
      _message('Round ${index + 1} copied — paste it in the target app');
    }
  }

  Future<void> _eject() async {
    if (widget.board.itemAt(selectedIndex) == null) return;
    await widget.board.eject(selectedIndex);
    HapticFeedback.mediumImpact();
  }

  void _message(String message, {bool error = false}) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: error ? const Color(0xFFE56B6F) : panelRaised,
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    final selected = widget.board.itemAt(selectedIndex);
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _Header(loaded: widget.board.loadedCount, onCapture: _capture),
            const _InstructionStrip(),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 760;
                  final revolver = Revolver(
                    items: widget.board.items,
                    selectedIndex: selectedIndex,
                    onSelected: _copy,
                  );
                  final detail = _RoundDetail(
                    index: selectedIndex,
                    content: selected,
                    onCopy:
                        selected == null ? null : () => _copy(selectedIndex),
                    onEject: selected == null ? null : _eject,
                  );
                  if (wide) {
                    return Padding(
                      padding: const EdgeInsets.all(20),
                      child: Row(
                        children: [
                          Expanded(flex: 3, child: revolver),
                          const SizedBox(width: 16),
                          Expanded(flex: 2, child: detail),
                        ],
                      ),
                    );
                  }
                  return SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(14, 14, 14, 24),
                    child: Column(
                      children: [
                        SizedBox(
                          height: math.min(constraints.maxWidth, 440.0),
                          child: revolver,
                        ),
                        const SizedBox(height: 14),
                        detail,
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.loaded, required this.onCapture});

  final int loaded;
  final VoidCallback onCapture;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 12),
      child: Row(
        children: [
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'COPYBOARD',
                  style: TextStyle(
                    fontSize: 23,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.5,
                  ),
                ),
                Text(
                  'TEN-CHAMBER CLIPBOARD  /  MOBILE',
                  style: TextStyle(
                    color: brass,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          Text('$loaded / 10', style: const TextStyle(color: textDim)),
          const SizedBox(width: 10),
          FilledButton.icon(
            onPressed: onCapture,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('CAPTURE'),
            style: FilledButton.styleFrom(
              backgroundColor: orange,
              foregroundColor: ink,
              textStyle: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _InstructionStrip extends StatelessWidget {
  const _InstructionStrip();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: panelRaised,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 9),
      child: const Text(
        'TAP TO COPY   •   HOLD + DRAG INTO ANOTHER APP   •   KEYBOARD MODE INSERTS DIRECTLY',
        textAlign: TextAlign.center,
        style: TextStyle(
          color: textDim,
          fontSize: 9,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class Revolver extends StatelessWidget {
  const Revolver({
    super.key,
    required this.items,
    required this.selectedIndex,
    required this.onSelected,
  });

  final List<String> items;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: panel,
        border: Border.all(color: line),
        borderRadius: BorderRadius.circular(18),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final size = math.min(constraints.maxWidth, constraints.maxHeight);
          final center = Offset(
            constraints.maxWidth / 2,
            constraints.maxHeight / 2,
          );
          final ringRadius = size * 0.34;
          final chamberSize = (size * 0.155).clamp(52.0, 76.0).toDouble();
          return Stack(
            clipBehavior: Clip.none,
            children: [
              Positioned.fromRect(
                rect: Rect.fromCircle(center: center, radius: size * 0.43),
                child: const DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: panelRaised,
                    border: Border.fromBorderSide(
                      BorderSide(color: line, width: 2),
                    ),
                  ),
                ),
              ),
              for (var index = 0; index < BoardStore.chamberCount; index++)
                _positionedChamber(
                  center: center,
                  radius: ringRadius,
                  size: chamberSize,
                  index: index,
                ),
              Positioned(
                left: center.dx - size * 0.15,
                top: center.dy - size * 0.15,
                width: size * 0.30,
                height: size * 0.30,
                child: DecoratedBox(
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: ink,
                    border: Border.fromBorderSide(
                      BorderSide(color: brass, width: 2),
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        items.length.toString().padLeft(2, '0'),
                        style: TextStyle(
                          fontSize: size * 0.075,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const Text(
                        '/ 10 LOADED',
                        style: TextStyle(color: brass, fontSize: 8),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _positionedChamber({
    required Offset center,
    required double radius,
    required double size,
    required int index,
  }) {
    final angle = -math.pi / 2 + index * 2 * math.pi / BoardStore.chamberCount;
    final x = center.dx + radius * math.cos(angle) - size / 2;
    final y = center.dy + radius * math.sin(angle) - size / 2;
    final content = index < items.length ? items[index] : null;
    final chamber = _Chamber(
      index: index,
      content: content,
      selected: selectedIndex == index,
      onTap: content == null ? null : () => onSelected(index),
    );
    return Positioned(
      left: x,
      top: y,
      width: size,
      height: size,
      child: chamber,
    );
  }
}

class _Chamber extends StatelessWidget {
  const _Chamber({
    required this.index,
    required this.content,
    required this.selected,
    required this.onTap,
  });

  final int index;
  final String? content;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final body = Semantics(
      button: content != null,
      label: content == null
          ? 'Empty chamber ${index + 1}'
          : 'Copy chamber ${index + 1}',
      child: Material(
        color: selected ? orange : panelSoft,
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          child: Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: selected ? orange : line,
                width: selected ? 3 : 2,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  (index + 1).toString().padLeft(2, '0'),
                  style: TextStyle(
                    color:
                        selected ? ink : (content == null ? textFaint : brass),
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text(
                  content == null ? '—' : _mark(content!),
                  style: TextStyle(
                    color: selected ? ink : paper,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    if (content == null) return body;
    return DragItemWidget(
      dragItemProvider: (_) async {
        final item = DragItem(localData: index);
        item.add(Formats.plainText(content!));
        return item;
      },
      allowedOperations: () => [DropOperation.copy],
      child: DraggableWidget(child: body),
    );
  }

  static String _mark(String content) {
    final trimmed = content.trimLeft();
    if (Uri.tryParse(trimmed)?.isAbsolute == true &&
        (trimmed.startsWith('http://') || trimmed.startsWith('https://'))) {
      return '↗';
    }
    if (content.contains('\n') && RegExp(r'[{}();=<>]').hasMatch(content)) {
      return '{ }';
    }
    if (content.contains('\n')) {
      return '¶';
    }
    return 'T';
  }
}

class _RoundDetail extends StatelessWidget {
  const _RoundDetail({
    required this.index,
    required this.content,
    required this.onCopy,
    required this.onEject,
  });

  final int index;
  final String? content;
  final VoidCallback? onCopy;
  final VoidCallback? onEject;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 190),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: panel,
        border: Border.all(color: line),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'CHAMBER ${(index + 1).toString().padLeft(2, '0')} / 10',
            style: const TextStyle(
              color: orange,
              fontSize: 10,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 12),
          SelectableText(
            content ?? 'Empty chamber',
            maxLines: 7,
            style: TextStyle(
              color: content == null ? textFaint : paper,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: onCopy,
                  icon: const Icon(Icons.copy, size: 17),
                  label: const Text('COPY ROUND'),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: onEject,
                tooltip: 'Eject round',
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
