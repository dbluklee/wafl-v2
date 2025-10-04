// 공통 JavaScript 함수들

// 토스트 알림 표시
function showToast(type, message, duration = 4000) {
    const toast = document.getElementById('toast');
    const toastContent = document.getElementById('toast-content');
    const toastIcon = document.getElementById('toast-icon');
    const toastMessage = document.getElementById('toast-message');

    // 아이콘 설정
    let iconColor, bgColor, borderColor, icon;

    switch (type) {
        case 'success':
            iconColor = 'text-green-600';
            bgColor = 'bg-green-50';
            borderColor = 'border-green-200';
            icon = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                    </svg>`;
            break;
        case 'error':
            iconColor = 'text-red-600';
            bgColor = 'bg-red-50';
            borderColor = 'border-red-200';
            icon = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>`;
            break;
        case 'warning':
            iconColor = 'text-yellow-600';
            bgColor = 'bg-yellow-50';
            borderColor = 'border-yellow-200';
            icon = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>`;
            break;
        default:
            iconColor = 'text-blue-600';
            bgColor = 'bg-blue-50';
            borderColor = 'border-blue-200';
            icon = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
                    </svg>`;
    }

    // 스타일 적용
    toastContent.className = `${bgColor} ${borderColor} border rounded-lg shadow-lg p-4 max-w-sm`;
    toastIcon.className = `flex-shrink-0 w-6 h-6 mr-3 ${iconColor}`;
    toastIcon.innerHTML = icon;
    toastMessage.textContent = message;

    // 토스트 표시
    toast.classList.remove('hidden');
    toast.classList.add('toast-enter');

    // 자동 숨김
    setTimeout(() => {
        hideToast();
    }, duration);
}

function hideToast() {
    const toast = document.getElementById('toast');
    toast.classList.add('toast-exit');

    setTimeout(() => {
        toast.classList.add('hidden');
        toast.classList.remove('toast-enter', 'toast-exit');
    }, 300);
}

// 로딩 상태 표시
function showLoading(element, text = '로딩 중...') {
    const originalContent = element.innerHTML;
    element.dataset.originalContent = originalContent;
    element.innerHTML = `
        <svg class="spinner w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        ${text}
    `;
    element.disabled = true;
}

function hideLoading(element) {
    element.innerHTML = element.dataset.originalContent;
    element.disabled = false;
}

// API 요청 헬퍼
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API 요청 오류:', error);
        throw error;
    }
}

// 폼 검증 헬퍼
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('border-red-500');
            isValid = false;
        } else {
            input.classList.remove('border-red-500');
        }
    });

    return isValid;
}

// 날짜 포맷팅
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 숫자 포맷팅 (천 단위 콤마)
function formatNumber(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// 텍스트 자르기
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
}

// 모달 제어
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = 'auto';
    }
}

// 전역 이벤트 리스너
document.addEventListener('DOMContentLoaded', function() {
    // 모달 외부 클릭 시 닫기
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-backdrop')) {
            e.target.closest('.modal').classList.add('hidden');
            document.body.style.overflow = 'auto';
        }
    });

    // ESC 키로 모달 닫기
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal:not(.hidden)');
            openModals.forEach(modal => {
                modal.classList.add('hidden');
            });
            document.body.style.overflow = 'auto';
        }
    });

    // 토스트 클릭 시 닫기
    document.getElementById('toast')?.addEventListener('click', hideToast);
});

// 전역 오류 처리
window.addEventListener('unhandledrejection', function(event) {
    console.error('처리되지 않은 Promise 오류:', event.reason);
    showToast('error', '예상치 못한 오류가 발생했습니다.');
});

// 네트워크 상태 모니터링
window.addEventListener('online', function() {
    showToast('success', '인터넷 연결이 복구되었습니다.');
});

window.addEventListener('offline', function() {
    showToast('warning', '인터넷 연결이 끊어졌습니다.');
});