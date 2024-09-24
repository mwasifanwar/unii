function sendMessage() {
    const userInput = document.getElementById('user-input').value;
    const chatOutput = document.getElementById('chat-output');

    // Append user's message to chat output
    const userMessage = document.createElement('div');
    userMessage.className = 'user-message';
    userMessage.textContent = userInput;
    chatOutput.appendChild(userMessage);

    // Scroll to the bottom
    chatOutput.scrollTop = chatOutput.scrollHeight;

    // Simulate bot response (for testing purposes)
    setTimeout(() => {
        const botMessage = document.createElement('div');
        botMessage.className = 'bot-message';
        botMessage.textContent = 'This is a simulated response from the bot.';
        chatOutput.appendChild(botMessage);
        chatOutput.scrollTop = chatOutput.scrollHeight;
    }, 1000);

    // Clear input
    document.getElementById('user-input').value = '';
}
