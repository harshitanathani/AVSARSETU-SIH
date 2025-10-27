// Test script to verify frontend-backend connection
fetch('http://localhost:4000/api/health')
  .then(response => response.json())
  .then(data => console.log('Backend connection successful:', data))
  .catch(error => console.error('Backend connection failed:', error));

// Test registration
fetch('http://localhost:4000/api/auth/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'Test User',
    email: 'test@example.com',
    password: 'password123',
    location: 'Delhi',
    skills: 'JavaScript,Python',
    interests: 'Web Development'
  })
})
.then(response => response.json())
.then(data => console.log('Registration successful:', data))
.catch(error => console.error('Registration failed:', error));