const tabs = document.querySelectorAll('.tab');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

function setTab(tab) {
  tabs.forEach((t) => t.classList.remove('active'));
  tab.classList.add('active');
  const target = tab.dataset.tab;
  if (target === 'login') {
    loginForm.classList.remove('hidden');
    registerForm.classList.add('hidden');
  } else {
    registerForm.classList.remove('hidden');
    loginForm.classList.add('hidden');
  }
}

tabs.forEach((tab) => {
  tab.addEventListener('click', () => setTab(tab));
});

document.getElementById('loginBtn').addEventListener('click', () => {
  window.location.href = '/';
});

document.getElementById('registerBtn').addEventListener('click', () => {
  window.location.href = '/';
});
