// Copyboard Browser Extension - Background Script

const extensionId = chrome.runtime.id;
console.log('Extension ID:', extensionId);
console.log('Manifest:', JSON.stringify(chrome.runtime.getManifest()));

// Save ID to storage for reference
chrome.storage.local.set({ extensionId: extensionId });

// Debug logging function
function logDebug(message) {
  console.log('[Copyboard Debug]', message);
}

function chamberLabel(index) {
  return String(index + 1).padStart(2, '0');
}

// Helper function to truncate text
function truncateText(text, maxLength) {
  if (!text) return "";
  if (text.length <= maxLength) {
    return text;
  }
  return text.substr(0, maxLength) + "...";
}

function showBadge(text, color) {
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color || "#4285F4" });
  if (text) {
    setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1800);
  }
}

// The complete menu tree is built once per install.  Refreshing the paste
// rounds removes and recreates only the "copyboard-paste" parent, never the
// whole tree: removeAll() here would delete Copyboard's own menu entries.
function createContextMenus() {
  chrome.contextMenus.removeAll(() => {
    void chrome.runtime.lastError;
    chrome.contextMenus.create({
      id: "copyboard-main",
      title: "Copyboard",
      contexts: ["all"]
    });
    chrome.contextMenus.create({
      id: "copyboard-add",
      parentId: "copyboard-main",
      title: "Copy to Clipboard Board",
      contexts: ["selection"]
    });
    chrome.contextMenus.create({
      id: "copyboard-paste",
      parentId: "copyboard-main",
      title: "Paste from Clipboard Board",
      contexts: ["editable"]
    });
    chrome.contextMenus.create({
      id: "copyboard-radial",
      parentId: "copyboard-main",
      title: "Paste with Radial Menu",
      contexts: ["editable"]
    });
    // Populate the paste submenu only after the tree above exists.
    refreshBoardMenu();
  });
}

function rebuildPasteMenu(items) {
  chrome.contextMenus.remove("copyboard-paste", () => {
    void chrome.runtime.lastError;
    chrome.contextMenus.create({
      id: "copyboard-paste",
      parentId: "copyboard-main",
      title: "Paste from Clipboard Board",
      contexts: ["editable"]
    });
    (items || []).slice(0, 16).forEach((item, index) => {
      chrome.contextMenus.create({
        id: `copyboard-item-${index}`,
        parentId: "copyboard-paste",
        title: `${chamberLabel(index)}  ${truncateText(item, 32)}`,
        contexts: ["editable"]
      });
    });
  });
}

// Refresh the paste submenu quietly.  Service workers may restart at any
// time, so this runs on install, on browser startup, and after board writes.
function refreshBoardMenu() {
  chrome.runtime.sendNativeMessage(
    "com.copyboard.extension",
    { action: "list" },
    (response) => {
      if (chrome.runtime.lastError) {
        logDebug('Could not refresh paste menu: ' + chrome.runtime.lastError.message);
        return;
      }
      if (response && Array.isArray(response.items)) {
        rebuildPasteMenu(response.items);
      }
    }
  );
}

chrome.runtime.onInstalled.addListener(() => {
  logDebug('Extension installed/updated');
  createContextMenus();
});

chrome.runtime.onStartup.addListener(() => {
  refreshBoardMenu();
});

// Listen for messages from content script and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  logDebug('Received message: ' + JSON.stringify(message));

  if (message.action === "get-clipboard-items") {
    sendNativeMessage({ action: "list" }, (response) => {
      if (response && response.items) {
        logDebug('Retrieved clipboard items: ' + response.items.length);
        sendResponse({ items: response.items });
      } else {
        logDebug('No clipboard items or error in response');
        sendResponse({ items: [] });
      }
    });
    return true; // Indicate we'll respond asynchronously
  }

  if (message.action === "add-to-board") {
    sendNativeMessage({ action: "add", content: message.content }, (response) => {
      if (response && response.success) {
        refreshBoardMenu();
      }
      sendResponse({ success: !!(response && response.success) });
    });
    return true;
  }

  if (message.action === "clear-board") {
    sendNativeMessage({ action: "clear" }, (response) => {
      if (response && response.success) {
        refreshBoardMenu();
      }
      sendResponse({ success: !!(response && response.success) });
    });
    return true;
  }
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  logDebug('Context menu clicked: ' + info.menuItemId);

  switch (info.menuItemId) {
    case "copyboard-add":
      if (info.selectionText) {
        logDebug('Adding text to clipboard board: ' + truncateText(info.selectionText, 30));
        sendNativeMessage({ action: "add", content: info.selectionText }, (response) => {
          if (response && response.success) {
            showBadge("✓", "#4CAF50");
            refreshBoardMenu();
          }
        });
      }
      break;

    case "copyboard-paste":
      // The submenu is kept warm after every board write.  This path is the
      // fallback for an empty or stale menu: refresh it for the next open and
      // tell the user which way to go instead of wiping the menu tree.
      sendNativeMessage({ action: "list" }, (response) => {
        const items = response && Array.isArray(response.items) ? response.items : [];
        if (items.length === 0) {
          showBadge("0", "#FF9800");
          logDebug('No clipboard items found');
        } else {
          rebuildPasteMenu(items);
          showBadge("↓", "#4285F4");
        }
      });
      break;

    case "copyboard-radial":
      logDebug('Showing radial menu');
      chrome.tabs.sendMessage(tab.id, { action: "show-radial" }, () => {
        void chrome.runtime.lastError;
      });
      break;

    default:
      if (info.menuItemId.startsWith("copyboard-item-")) {
        const index = parseInt(info.menuItemId.split("-")[2], 10);
        logDebug('Pasting clipboard item at index: ' + index);
        sendNativeMessage({ action: "paste", index: index }, (response) => {
          if (response && response.content) {
            logDebug('Retrieved content from native host, sending to content script');
            chrome.tabs.sendMessage(tab.id, {
              action: "paste-content",
              content: response.content
            }, () => {
              void chrome.runtime.lastError;
            });
          } else {
            logDebug('Failed to retrieve content from native host');
          }
        });
      }
      break;
  }
});

// Native messaging with host
function sendNativeMessage(message, callback) {
  logDebug('Sending native message: ' + JSON.stringify(message));
  chrome.action.setBadgeText({ text: "..." });
  chrome.action.setBadgeBackgroundColor({ color: "#4285F4" });

  try {
    chrome.runtime.sendNativeMessage(
      "com.copyboard.extension",
      message,
      (response) => {
        chrome.action.setBadgeText({ text: "" });

        if (chrome.runtime.lastError) {
          const errorMessage = chrome.runtime.lastError.message;
          logDebug('Error sending native message: ' + errorMessage);
          chrome.action.setBadgeText({ text: "!" });
          chrome.action.setBadgeBackgroundColor({ color: "#F44336" });
          setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 3000);

          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon128.png',
            title: 'Copyboard Error',
            message: 'Native messaging error: ' + errorMessage.substring(0, 100)
          });

          callback && callback(null);
        } else {
          logDebug('Native message response: ' + JSON.stringify(response));

          if (response && response.success) {
            chrome.action.setBadgeText({ text: "✓" });
            chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
            setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1500);
          } else if (response) {
            chrome.action.setBadgeText({ text: "!" });
            chrome.action.setBadgeBackgroundColor({ color: "#FF9800" });
            setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1500);
            logDebug('Response indicates error: ' + (response.error || 'Unknown error'));
          }

          callback && callback(response);
        }
      }
    );
  } catch (e) {
    logDebug('Exception sending native message: ' + e.message);
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#F44336" });
    setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 3000);
    callback && callback(null);
  }
}
