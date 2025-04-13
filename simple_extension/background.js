// Simple Native Messaging Test

// Log extension ID
console.log("Extension ID:", chrome.runtime.id);

// Function to test native messaging
function testNativeMessaging() {
  console.log("Testing native messaging connection...");
  
  try {
    chrome.runtime.sendNativeMessage(
      "com.copyboard.extension",
      { action: "ping", timestamp: Date.now() },
      (response) => {
        if (chrome.runtime.lastError) {
          console.error("Native messaging error:", chrome.runtime.lastError.message);
        } else {
          console.log("Response from native host:", response);
        }
      }
    );
  } catch (e) {
    console.error("Exception sending native message:", e);
  }
}

// Listen for extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log("Extension started");
  // Test after a short delay
  setTimeout(testNativeMessaging, 1000);
});

// Listen for install/update
chrome.runtime.onInstalled.addListener(() => {
  console.log("Extension installed or updated");
  // Test after a short delay
  setTimeout(testNativeMessaging, 1000);
});

// Also test on service worker activation (this helps when debugging)
console.log("Service worker activating");
setTimeout(testNativeMessaging, 1000);
