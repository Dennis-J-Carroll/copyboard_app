import 'package:copyboard_mobile/main.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('board keeps the newest ten rounds', () async {
    final board = await BoardStore.load();
    for (var index = 0; index < 12; index++) {
      await board.loadRound('round-$index');
    }

    expect(board.loadedCount, BoardStore.chamberCount);
    expect(board.itemAt(0), 'round-11');
    expect(board.itemAt(9), 'round-2');
  });

  testWidgets('renders the ten-chamber revolver', (tester) async {
    final board = await BoardStore.load();
    await board.loadRound('A useful saved round');

    await tester.pumpWidget(CopyBoardApp(board: board));
    await tester.pumpAndSettle();

    expect(find.text('COPYBOARD'), findsOneWidget);
    expect(find.text('1 / 10'), findsOneWidget);
    expect(find.text('A useful saved round'), findsOneWidget);
    expect(find.text('10'), findsOneWidget);
  });
}
