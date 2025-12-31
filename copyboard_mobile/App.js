/**
 * CopyBoard Mobile - Multi-Clipboard App
 *
 * Features:
 * - Store 1-10+ clipboard items (user configurable)
 * - Hold and drag to select which item to paste
 * - Visual feedback with haptics
 * - Persistent storage
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  SafeAreaView,
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  Alert,
  StatusBar,
  Animated,
  PanResponder,
} from 'react-native';
import Clipboard from '@react-native-clipboard/clipboard';
import AsyncStorage from '@react-native-async-storage/async-storage';
import ReactNativeHapticFeedback from 'react-native-haptic-feedback';

const STORAGE_KEY = '@copyboard_items';
const MAX_ITEMS_KEY = '@copyboard_max_items';
const DEFAULT_MAX_ITEMS = 10;

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

function App() {
  const [clipboardItems, setClipboardItems] = useState([]);
  const [maxItems, setMaxItems] = useState(DEFAULT_MAX_ITEMS);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isDragging, setIsDragging] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Animation values
  const dragY = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // Load saved items on mount
  useEffect(() => {
    loadClipboardItems();
    loadMaxItems();
    startClipboardMonitoring();
  }, []);

  // Load clipboard items from storage
  const loadClipboardItems = async () => {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEY);
      if (stored) {
        setClipboardItems(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Error loading clipboard items:', error);
    }
  };

  // Load max items setting
  const loadMaxItems = async () => {
    try {
      const stored = await AsyncStorage.getItem(MAX_ITEMS_KEY);
      if (stored) {
        setMaxItems(parseInt(stored, 10));
      }
    } catch (error) {
      console.error('Error loading max items:', error);
    }
  };

  // Save clipboard items to storage
  const saveClipboardItems = async (items) => {
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      console.error('Error saving clipboard items:', error);
    }
  };

  // Save max items setting
  const saveMaxItems = async (value) => {
    try {
      await AsyncStorage.setItem(MAX_ITEMS_KEY, value.toString());
      setMaxItems(value);
    } catch (error) {
      console.error('Error saving max items:', error);
    }
  };

  // Monitor clipboard for new items
  const startClipboardMonitoring = () => {
    // Note: In production, you'd use a background task or listener
    // For now, we'll add items manually via the "Copy" button
  };

  // Add item to clipboard board
  const addClipboardItem = async () => {
    try {
      const content = await Clipboard.getString();

      if (!content || content.trim() === '') {
        Alert.alert('Empty Clipboard', 'Nothing to copy!');
        return;
      }

      // Don't add duplicates at the top
      if (clipboardItems.length > 0 && clipboardItems[0] === content) {
        Alert.alert('Already Added', 'This item is already at the top!');
        return;
      }

      // Add to the top of the list
      const newItems = [content, ...clipboardItems];

      // Limit to max items
      const trimmedItems = newItems.slice(0, maxItems);

      setClipboardItems(trimmedItems);
      await saveClipboardItems(trimmedItems);

      // Haptic feedback
      ReactNativeHapticFeedback.trigger('impactLight');

      Alert.alert('Added!', `Copied to board (${trimmedItems.length}/${maxItems})`);
    } catch (error) {
      Alert.alert('Error', 'Failed to add clipboard item');
      console.error(error);
    }
  };

  // Paste item from board
  const pasteItem = async (index) => {
    if (index < 0 || index >= clipboardItems.length) return;

    try {
      const item = clipboardItems[index];
      await Clipboard.setString(item);

      // Haptic feedback
      ReactNativeHapticFeedback.trigger('notificationSuccess');

      Alert.alert('Copied to Clipboard!', `Item ${index + 1} ready to paste`);
    } catch (error) {
      Alert.alert('Error', 'Failed to copy to clipboard');
      console.error(error);
    }
  };

  // Remove item from board
  const removeItem = (index) => {
    Alert.alert(
      'Remove Item',
      `Remove item ${index + 1}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            const newItems = clipboardItems.filter((_, i) => i !== index);
            setClipboardItems(newItems);
            await saveClipboardItems(newItems);
            ReactNativeHapticFeedback.trigger('impactMedium');
          },
        },
      ]
    );
  };

  // Clear all items
  const clearAll = () => {
    Alert.alert(
      'Clear All',
      'Remove all clipboard items?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            setClipboardItems([]);
            await saveClipboardItems([]);
            ReactNativeHapticFeedback.trigger('notificationWarning');
          },
        },
      ]
    );
  };

  // Pan responder for drag gesture
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        setIsDragging(true);
        Animated.spring(scaleAnim, {
          toValue: 1.05,
          useNativeDriver: true,
        }).start();
      },
      onPanResponderMove: (evt, gestureState) => {
        dragY.setValue(gestureState.dy);

        // Calculate which item is selected based on drag position
        const itemHeight = 80; // Approximate height of each item
        const index = Math.floor(Math.abs(gestureState.dy) / itemHeight);
        const clampedIndex = Math.min(index, clipboardItems.length - 1);

        if (clampedIndex !== selectedIndex && clampedIndex >= 0) {
          setSelectedIndex(clampedIndex);
          ReactNativeHapticFeedback.trigger('impactLight');
        }
      },
      onPanResponderRelease: (evt, gestureState) => {
        setIsDragging(false);
        Animated.parallel([
          Animated.spring(dragY, {
            toValue: 0,
            useNativeDriver: true,
          }),
          Animated.spring(scaleAnim, {
            toValue: 1,
            useNativeDriver: true,
          }),
        ]).start();

        // Paste the selected item
        if (selectedIndex >= 0 && selectedIndex < clipboardItems.length) {
          pasteItem(selectedIndex);
        }

        setSelectedIndex(-1);
      },
    })
  ).current;

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#1a1a2e" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📋 CopyBoard</Text>
        <Text style={styles.headerSubtitle}>
          {clipboardItems.length}/{maxItems} items
        </Text>
        <TouchableOpacity
          style={styles.settingsButton}
          onPress={() => setShowSettings(!showSettings)}
        >
          <Text style={styles.settingsIcon}>⚙️</Text>
        </TouchableOpacity>
      </View>

      {/* Settings Panel */}
      {showSettings && (
        <View style={styles.settingsPanel}>
          <Text style={styles.settingsTitle}>Max Items</Text>
          <View style={styles.maxItemsSelector}>
            {[5, 6, 7, 8, 9, 10, 12, 15, 20].map((num) => (
              <TouchableOpacity
                key={num}
                style={[
                  styles.maxItemButton,
                  maxItems === num && styles.maxItemButtonActive,
                ]}
                onPress={() => saveMaxItems(num)}
              >
                <Text
                  style={[
                    styles.maxItemButtonText,
                    maxItems === num && styles.maxItemButtonTextActive,
                  ]}
                >
                  {num}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Instructions */}
      <View style={styles.instructions}>
        <Text style={styles.instructionsText}>
          👆 Tap item to copy • Long press to remove
        </Text>
        <Text style={styles.instructionsText}>
          👇 Hold & drag down to select while pasting
        </Text>
      </View>

      {/* Action Buttons */}
      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.addButton} onPress={addClipboardItem}>
          <Text style={styles.buttonText}>➕ Add from Clipboard</Text>
        </TouchableOpacity>
        {clipboardItems.length > 0 && (
          <TouchableOpacity style={styles.clearButton} onPress={clearAll}>
            <Text style={styles.clearButtonText}>🗑️ Clear All</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Clipboard Items List */}
      <ScrollView style={styles.scrollView}>
        {clipboardItems.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateIcon}>📋</Text>
            <Text style={styles.emptyStateText}>No clipboard items yet</Text>
            <Text style={styles.emptyStateSubtext}>
              Copy something, then tap "Add from Clipboard"
            </Text>
          </View>
        ) : (
          clipboardItems.map((item, index) => (
            <Animated.View
              key={`${index}-${item.substring(0, 20)}`}
              style={[
                styles.clipboardItem,
                selectedIndex === index && isDragging && styles.clipboardItemSelected,
                {
                  transform: [
                    {
                      scale: selectedIndex === index && isDragging ? scaleAnim : 1,
                    },
                  ],
                },
              ]}
              {...(index === 0 ? panResponder.panHandlers : {})}
            >
              <TouchableOpacity
                style={styles.itemContent}
                onPress={() => pasteItem(index)}
                onLongPress={() => removeItem(index)}
                delayLongPress={500}
              >
                <View style={styles.itemHeader}>
                  <Text style={styles.itemNumber}>{index + 1}</Text>
                  <Text style={styles.itemTimestamp}>
                    {index === 0 ? '📌 Most Recent' : `Item ${index + 1}`}
                  </Text>
                </View>
                <Text style={styles.itemText} numberOfLines={3}>
                  {item}
                </Text>
              </TouchableOpacity>
            </Animated.View>
          ))
        )}
      </ScrollView>

      {/* Drag Indicator */}
      {isDragging && (
        <View style={styles.dragIndicator}>
          <Text style={styles.dragIndicatorText}>
            📍 Release to paste item {selectedIndex + 1}
          </Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  header: {
    padding: 20,
    paddingTop: 10,
    backgroundColor: '#16213e',
    borderBottomWidth: 1,
    borderBottomColor: '#0f3460',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#e94560',
    marginBottom: 5,
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#8b98a8',
  },
  settingsButton: {
    position: 'absolute',
    right: 20,
    top: 15,
  },
  settingsIcon: {
    fontSize: 28,
  },
  settingsPanel: {
    backgroundColor: '#16213e',
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#0f3460',
  },
  settingsTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  maxItemsSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  maxItemButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#0f3460',
    borderWidth: 1,
    borderColor: '#1a5490',
  },
  maxItemButtonActive: {
    backgroundColor: '#e94560',
    borderColor: '#e94560',
  },
  maxItemButtonText: {
    color: '#8b98a8',
    fontSize: 14,
    fontWeight: '600',
  },
  maxItemButtonTextActive: {
    color: '#fff',
  },
  instructions: {
    padding: 15,
    backgroundColor: '#0f3460',
  },
  instructionsText: {
    color: '#8b98a8',
    fontSize: 12,
    marginBottom: 3,
  },
  buttonRow: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
  },
  addButton: {
    flex: 1,
    backgroundColor: '#e94560',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  clearButton: {
    backgroundColor: '#533483',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
    minWidth: 100,
  },
  clearButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyStateIcon: {
    fontSize: 64,
    marginBottom: 20,
  },
  emptyStateText: {
    color: '#8b98a8',
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  emptyStateSubtext: {
    color: '#5a6a7a',
    fontSize: 14,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  clipboardItem: {
    backgroundColor: '#16213e',
    marginHorizontal: 15,
    marginVertical: 6,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#0f3460',
    overflow: 'hidden',
  },
  clipboardItemSelected: {
    borderColor: '#e94560',
    borderWidth: 2,
    backgroundColor: '#1f2a47',
  },
  itemContent: {
    padding: 15,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  itemNumber: {
    backgroundColor: '#e94560',
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginRight: 10,
  },
  itemTimestamp: {
    color: '#8b98a8',
    fontSize: 12,
  },
  itemText: {
    color: '#fff',
    fontSize: 14,
    lineHeight: 20,
  },
  dragIndicator: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: '#e94560',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  dragIndicatorText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default App;
