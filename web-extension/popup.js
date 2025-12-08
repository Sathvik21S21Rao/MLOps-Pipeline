document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const resultDiv = document.getElementById('result');
  resultDiv.innerText = "Scanning...";
  resultDiv.className = "";

  // 1. Get the current active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // 2. Send message to content.js to extract text
  chrome.tabs.sendMessage(tab.id, { action: "scrape_email" }, async (response) => {
    
    // Check for scraping errors
    if (chrome.runtime.lastError || !response || !response.success) {
      console.error("Scraping failed:", chrome.runtime.lastError);
      resultDiv.innerText = "Error: Could not read email.";
      resultDiv.className = "error";
      return;
    }

    const emailContent = response.text;

    // --- LOG 1: Print the text we are sending ---
    console.log("--------------------------------");
    console.log("SENDING TEXT (Length: " + emailContent.length + "):");
    console.log(emailContent.substring(0, 150) + "..."); // Print first 150 chars
    console.log("--------------------------------");

    try {
      // 3. Send text to your server
      const apiResponse = await fetch("http://localhost:8000/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email_text: emailContent })
      });

      if (!apiResponse.ok) throw new Error(`Server error: ${apiResponse.status}`);

      const data = await apiResponse.json();
      
      // --- LOG 2: Print the exact object received ---
      console.log("RECEIVED RESPONSE:");
      console.log(data); 
      // Expected: {predicted_label: 3, input_length: 1860, model_used: 'sgd', label: 'Forum'}
      console.log("--------------------------------");

      // 4. Display Prediction
      // We use data.label because that contains the text "Forum"
      resultDiv.innerHTML = `
        <div style="font-size: 1.2em; color: #333;">Category: <strong>${data.label}</strong></div>
        <div style="font-size: 0.8em; color: #666; margin-top: 5px;">
          Model: ${data.model_used} <br>
          Input Length: ${data.input_length} chars
        </div>
      `;
      
    } catch (err) {
      console.error("Network Error:", err);
      resultDiv.innerText = "Error connecting to server.";
      resultDiv.className = "error";
    }
  });
});