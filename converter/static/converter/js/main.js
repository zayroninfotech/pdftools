document.addEventListener('DOMContentLoaded', function () {
    var config = window.PDFTOOLS_CONFIG || {};

    // ─── EMAIL MODAL ON PAGE OPEN ─────────────────────────────────────
    // Show email popup for all anonymous users when they open ANY page
    // They must submit email before using any tools.

    var emailModal = document.getElementById('emailModal');
    var submitEmailBtn = document.getElementById('submitEmailBtn');
    var anonymousEmailInput = document.getElementById('anonymousEmail');

    if (emailModal && !config.isAuthenticated && !config.hasEmail) {
        var modal = new bootstrap.Modal(emailModal);
        modal.show();
    }

    if (submitEmailBtn) {
        submitEmailBtn.addEventListener('click', function () {
            var email = anonymousEmailInput.value.trim();
            if (!email || email.indexOf('@') === -1 || email.indexOf('.') === -1) {
                anonymousEmailInput.classList.add('is-invalid');
                return;
            }
            anonymousEmailInput.classList.remove('is-invalid');
            submitEmailBtn.disabled = true;
            submitEmailBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Submitting...';

            fetch('/api/check-email/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken,
                },
                body: JSON.stringify({ email: email }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    config.hasEmail = true;
                    var bsModal = bootstrap.Modal.getInstance(emailModal);
                    if (bsModal) bsModal.hide();
                } else {
                    anonymousEmailInput.classList.add('is-invalid');
                    submitEmailBtn.disabled = false;
                    submitEmailBtn.innerHTML = '<i class="fas fa-arrow-right me-2"></i>Start Using Tools';
                }
            })
            .catch(function () {
                submitEmailBtn.disabled = false;
                submitEmailBtn.innerHTML = '<i class="fas fa-arrow-right me-2"></i>Start Using Tools';
            });
        });
    }

    if (anonymousEmailInput) {
        anonymousEmailInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitEmailBtn.click();
            }
        });
        // Auto focus
        if (emailModal) {
            emailModal.addEventListener('shown.bs.modal', function () {
                anonymousEmailInput.focus();
            });
        }
    }

    // ─── TOOL PAGE LOGIC ─────────────────────────────────────────────

    var uploadZone = document.getElementById('uploadZone');
    var fileInput = document.getElementById('fileInput');
    var selectBtn = document.getElementById('selectBtn');
    var fileList = document.getElementById('fileList');
    var fileListItems = document.getElementById('fileListItems');
    var clearFilesBtn = document.getElementById('clearFiles');
    var toolOptions = document.getElementById('toolOptions');
    var processSection = document.getElementById('processSection');
    var processBtn = document.getElementById('processBtn');
    var progressSection = document.getElementById('progressSection');
    var progressFill = document.getElementById('progressFill');
    var progressText = document.getElementById('progressText');
    var downloadSection = document.getElementById('downloadSection');
    var downloadBtn = document.getElementById('downloadBtn');
    var errorSection = document.getElementById('errorSection');
    var errorMessage = document.getElementById('errorMessage');
    var startOverBtn = document.getElementById('startOver');
    var tryAgainBtn = document.getElementById('tryAgain');
    var toolForm = document.getElementById('toolForm');

    if (!uploadZone) return; // Not on a tool page

    var selectedFiles = [];

    // ─── DRAG & DROP ─────────────────────────────────────────────────

    uploadZone.addEventListener('click', function (e) {
        if (e.target === selectBtn || selectBtn.contains(e.target)) return;
        fileInput.click();
    });

    selectBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        fileInput.click();
    });

    uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });

    uploadZone.addEventListener('dragleave', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
    });

    uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        var files = Array.from(e.dataTransfer.files);
        handleFiles(files);
    });

    fileInput.addEventListener('change', function () {
        var files = Array.from(fileInput.files);
        handleFiles(files);
    });

    // ─── FILE HANDLING ───────────────────────────────────────────────

    function handleFiles(files) {
        if (!fileInput.multiple) {
            selectedFiles = files.slice(0, 1);
        } else {
            selectedFiles = selectedFiles.concat(files);
        }
        updateFileList();
        showSections();
    }

    function updateFileList() {
        if (selectedFiles.length === 0) {
            fileList.classList.add('d-none');
            if (processSection) processSection.classList.add('d-none');
            if (toolOptions) toolOptions.classList.add('d-none');
            return;
        }

        fileListItems.innerHTML = '';
        selectedFiles.forEach(function (file, index) {
            var item = document.createElement('div');
            item.className = 'file-item fade-in';
            item.innerHTML =
                '<span class="file-item-name">' +
                    '<i class="fas fa-file-pdf"></i>' +
                    escapeHtml(file.name) +
                '</span>' +
                '<span class="file-item-size">' + formatSize(file.size) + '</span>';
            fileListItems.appendChild(item);
        });

        fileList.classList.remove('d-none');
    }

    function showSections() {
        if (selectedFiles.length > 0) {
            if (toolOptions) toolOptions.classList.remove('d-none');
            if (processSection) processSection.classList.remove('d-none');
            uploadZone.style.display = 'none';
        }
    }

    if (clearFilesBtn) {
        clearFilesBtn.addEventListener('click', function () {
            selectedFiles = [];
            fileInput.value = '';
            updateFileList();
            uploadZone.style.display = 'block';
            if (toolOptions) toolOptions.classList.add('d-none');
            if (processSection) processSection.classList.add('d-none');
        });
    }

    // ─── FORM SUBMISSION ─────────────────────────────────────────────

    if (toolForm) {
        toolForm.addEventListener('submit', function (e) {
            e.preventDefault();

            if (selectedFiles.length === 0) return;

            // Check if anonymous user needs email first
            if (!config.isAuthenticated && !config.hasEmail) {
                var modal = new bootstrap.Modal(emailModal);
                modal.show();
                return;
            }

            var formData = new FormData(toolForm);

            // Remove the original file input data and add our files
            formData.delete('files');
            selectedFiles.forEach(function (file) {
                formData.append('files', file);
            });

            // Show progress
            fileList.classList.add('d-none');
            if (toolOptions) toolOptions.classList.add('d-none');
            processSection.classList.add('d-none');
            progressSection.classList.remove('d-none');
            progressSection.classList.add('slide-up');
            errorSection.classList.add('d-none');
            downloadSection.classList.add('d-none');

            animateProgress();

            var xhr = new XMLHttpRequest();
            xhr.open('POST', window.location.pathname, true);
            // Add CSRF token header for Django
            xhr.setRequestHeader('X-CSRFToken', config.csrfToken);

            xhr.onload = function () {
                try {
                    var data = JSON.parse(xhr.responseText);

                    // Check for email requirement
                    if (data.need_email) {
                        clearInterval(progressInterval);
                        progressSection.classList.add('d-none');
                        resetFormDisplay();
                        var modal = new bootstrap.Modal(emailModal);
                        modal.show();
                        return;
                    }

                    if (xhr.status === 200 && data.success) {
                        completeProgress(function () {
                            showDownload(data.download_url);
                        });
                    } else {
                        showError(data.error || 'An unknown error occurred.');
                    }
                } catch (err) {
                    showError('Invalid response from server.');
                }
            };

            xhr.onerror = function () {
                showError('Network error. Please check your connection.');
            };

            xhr.send(formData);
        });
    }

    // ─── PROGRESS ANIMATION ──────────────────────────────────────────

    var progressInterval;

    function animateProgress() {
        var width = 0;
        progressFill.style.width = '0%';
        progressText.textContent = 'Processing your file...';

        progressInterval = setInterval(function () {
            if (width < 85) {
                width += Math.random() * 8 + 2;
                if (width > 85) width = 85;
                progressFill.style.width = width + '%';
            }

            if (width < 30) {
                progressText.textContent = 'Uploading file...';
            } else if (width < 60) {
                progressText.textContent = 'Processing your file...';
            } else {
                progressText.textContent = 'Almost done...';
            }
        }, 300);
    }

    function completeProgress(callback) {
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = 'Done!';
        setTimeout(callback, 500);
    }

    // ─── DOWNLOAD ────────────────────────────────────────────────────

    function showDownload(url) {
        progressSection.classList.add('d-none');
        downloadSection.classList.remove('d-none');
        downloadSection.classList.add('slide-up');
        downloadBtn.href = url;
    }

    // ─── ERROR ───────────────────────────────────────────────────────

    function showError(msg) {
        clearInterval(progressInterval);
        progressSection.classList.add('d-none');
        errorSection.classList.remove('d-none');
        errorSection.classList.add('slide-up');
        errorMessage.textContent = msg;
    }

    // ─── RESET ───────────────────────────────────────────────────────

    function resetFormDisplay() {
        uploadZone.style.display = 'block';
        if (toolOptions) toolOptions.classList.add('d-none');
        if (processSection) processSection.classList.add('d-none');
    }

    function resetAll() {
        selectedFiles = [];
        fileInput.value = '';
        updateFileList();
        uploadZone.style.display = 'block';
        if (toolOptions) toolOptions.classList.add('d-none');
        processSection.classList.add('d-none');
        progressSection.classList.add('d-none');
        downloadSection.classList.add('d-none');
        errorSection.classList.add('d-none');
    }

    if (startOverBtn) startOverBtn.addEventListener('click', resetAll);
    if (tryAgainBtn) tryAgainBtn.addEventListener('click', resetAll);

    // ─── TOOL-SPECIFIC INTERACTIONS ──────────────────────────────────

    // Split: Show/hide range input
    var splitRanges = document.getElementById('splitRanges');
    var splitAll = document.getElementById('splitAll');
    var rangesInput = document.getElementById('rangesInput');

    if (splitRanges && splitAll && rangesInput) {
        splitRanges.addEventListener('change', function () {
            rangesInput.classList.remove('d-none');
        });
        splitAll.addEventListener('change', function () {
            rangesInput.classList.add('d-none');
        });
    }

    // Rotate: Select degree
    document.querySelectorAll('.rotation-option').forEach(function (option) {
        option.addEventListener('click', function () {
            document.querySelectorAll('.rotation-option').forEach(function (o) {
                o.classList.remove('selected');
            });
            option.classList.add('selected');
            var degreesInput = document.getElementById('degreesInput');
            if (degreesInput) {
                degreesInput.value = option.dataset.degrees;
            }
        });
    });

    // Watermark: Opacity range display
    var opacityRange = document.getElementById('opacityRange');
    var opacityValue = document.getElementById('opacityValue');
    if (opacityRange && opacityValue) {
        opacityRange.addEventListener('input', function () {
            opacityValue.textContent = opacityRange.value;
        });
    }

    // Password: Toggle visibility
    var togglePassword = document.getElementById('togglePassword');
    var passwordInput = document.getElementById('passwordInput');
    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function () {
            var type = passwordInput.type === 'password' ? 'text' : 'password';
            passwordInput.type = type;
            togglePassword.querySelector('i').classList.toggle('fa-eye');
            togglePassword.querySelector('i').classList.toggle('fa-eye-slash');
        });
    }

    // ─── UTILITIES ───────────────────────────────────────────────────

    function formatSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
});
