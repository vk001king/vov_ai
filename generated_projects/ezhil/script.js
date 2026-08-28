document.addEventListener('DOMContentLoaded', () => {
    const todoInput = document.getElementById('todo-input');
    const addBtn = document.getElementById('add-btn');
    const todoList = document.getElementById('todo-list');
    const taskCount = document.getElementById('task-count');
    
    let todos = JSON.parse(localStorage.getItem('todos')) || [];
    
    function renderTodos() {
        todoList.innerHTML = '';
        
        if (todos.length === 0) {
            todoList.innerHTML = '<div class="empty-state">No tasks yet. Add one above!</div>';
        } else {
            todos.forEach((todo, index) => {
                const li = document.createElement('li');
                li.className = `todo-item ${todo.completed ? 'completed' : ''}`;
                li.dataset.index = index;
                li.innerHTML = `
                    <div class="checkbox ${todo.completed ? 'checked' : ''}" onclick="toggleTask(${index})"></div>
                    <span class="todo-text">${escapeHtml(todo.text)}</span>
                    <button class="delete-btn" onclick="deleteTask(${index})">Delete</button>
                `;
                todoList.appendChild(li);
            });
        }
        
        updateStats();
    }
    
    function addTask() {
        const text = todoInput.value.trim();
        if (!text) return;
        
        todos.push({ text, completed: false });
        saveTodos();
        renderTodos();
        todoInput.value = '';
    }
    
    function toggleTask(index) {
        todos[index].completed = !todos[index].completed;
        saveTodos();
        renderTodos();
    }
    
    function deleteTask(index) {
        todos.splice(index, 1);
        saveTodos();
        renderTodos();
    }
    
    function saveTodos() {
        localStorage.setItem('todos', JSON.stringify(todos));
    }
    
    function updateStats() {
        const total = todos.length;
        const completed = todos.filter(t => t.completed).length;
        const remaining = total - completed;
        taskCount.textContent = `${remaining} ${remaining === 1 ? 'task' : 'tasks'} left`;
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    addBtn.addEventListener('click', addTask);
    
    todoInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addTask();
        }
    });
    
    renderTodos();
});