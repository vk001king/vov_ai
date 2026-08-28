// Calculator Application Script
document.addEventListener('DOMContentLoaded', function() {
    const display = document.getElementById('display');
    const buttons = document.querySelectorAll('.btn');
    
    let currentExpression = '';
    let shouldResetDisplay = false;
    
    function updateDisplay() {
        display.textContent = currentExpression || '0';
    }
    
    function appendToDisplay(value) {
        if (shouldResetDisplay) {
            currentExpression = value;
            shouldResetDisplay = false;
        } else {
            if (currentExpression === '0' || currentExpression === '') {
                currentExpression = value;
            } else {
                currentExpression += value;
            }
        }
        updateDisplay();
    }
    
    function clearDisplay() {
        currentExpression = '';
        shouldResetDisplay = false;
        updateDisplay();
    }
    
    function deleteLast() {
        if (shouldResetDisplay) {
            return;
        }
        currentExpression = currentExpression.slice(0, -1);
        if (currentExpression === '') {
            currentExpression = '0';
        }
        updateDisplay();
    }
    
    function calculate() {
        try {
            // Replace visual operators with JavaScript operators
            let expression = currentExpression
                .replace(/×/g, '*')
                .replace(/÷/g, '/');
            
            // Evaluate the expression
            const result = eval(expression);
            
            currentExpression = result.toString();
            shouldResetDisplay = true;
            updateDisplay();
        } catch (error) {
            currentExpression = 'Error';
            shouldResetDisplay = true;
            updateDisplay();
            setTimeout(() => {
                currentExpression = '';
                shouldResetDisplay = false;
                updateDisplay();
            }, 2000);
        }
    }
    
    // Button click events
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            const action = this.dataset.action;
            const value = this.dataset.value;
            
            if (action === 'clear') {
                clearDisplay();
            } else if (action === 'delete') {
                deleteLast();
            } else if (action === 'calculate') {
                calculate();
            } else if (value) {
                appendToDisplay(value);
            }
        });
    });
    
    // Keyboard support
    document.addEventListener('keydown', function(event) {
        const key = event.key;
        
        if (key >= '0' && key <= '9') {
            appendToDisplay(key);
        } else if (key === '.') {
            appendToDisplay('.');
        } else if (key === '=' || key === 'Enter') {
            calculate();
        } else if (key === 'Backspace') {
            deleteLast();
        } else if (key === 'Escape') {
            clearDisplay();
        } else if (key === '+' || key === '-' || key === '*' || key === '/') {
            appendToDisplay(key);
        }
    });
});