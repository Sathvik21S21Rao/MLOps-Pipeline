// extension/content.js

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "scrape_email") {
    console.log("Gmail Scraper: Received request...");

    // Strategy 1: Standard message body class (.a3s)
    let messageBodies = document.querySelectorAll('.a3s');
    
    // Strategy 2: If .a3s fails, try the message wrapper (.ii.gt)
    if (messageBodies.length === 0) {
      console.log("Strategy 1 failed. Trying Strategy 2 (.ii.gt)...");
      messageBodies = document.querySelectorAll('.ii.gt');
    }

    // Strategy 3: Try role="listitem" (generic container for email threads)
    if (messageBodies.length === 0) {
       console.log("Strategy 2 failed. Trying Strategy 3 (expanded emails)...");
       // This looks for expanded messages in a thread
       messageBodies = document.querySelectorAll('.h7'); 
    }

    if (messageBodies.length > 0) {
      // Get the last visible message in the thread
      // We filter to ensure we only get elements with actual text
      const lastMessage = Array.from(messageBodies)
                               .filter(el => el.innerText && el.innerText.trim().length > 0)
                               .pop();
      
      if (lastMessage) {
        console.log("Success: Found email text.");
        // .innerText preserves newlines, .textContent does not.
        sendResponse({ success: true, text: lastMessage.innerText });
      } else {
         console.error("Found elements, but no text content.");
         sendResponse({ success: false, error: "Email body found but empty." });
      }
    } else {
      console.error("Error: No email body classes found in DOM.");
      sendResponse({ success: false, error: "No email body found. DOM query failed." });
    }
  }
  // Return true to indicate we wish to send a response asynchronously (optional here but good practice)
  return true; 
});