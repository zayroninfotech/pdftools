/**
 * Document Signer - 21 CFR Part 11 Compliant
 * Handles document upload, preview, signature placement, and signing.
 */
document.addEventListener('DOMContentLoaded', function () {
    var config = window.PDFTOOLS_CONFIG || {};

    // ─── ELEMENTS ────────────────────────────────────────────────────
    var uploadSection = document.getElementById('signerUploadSection');
    var uploadZone = document.getElementById('signerUploadZone');
    var selectBtn = document.getElementById('signerSelectBtn');
    var fileInput = document.getElementById('signerFileInput');

    var signerInterface = document.getElementById('signerInterface');
    var previewContainer = document.getElementById('previewContainer');
    var previewLoading = document.getElementById('previewLoading');
    var previewImage = document.getElementById('previewImage');
    var signatureMarker = document.getElementById('signatureMarker');
    var pageIndicator = document.getElementById('pageIndicator');
    var prevPageBtn = document.getElementById('prevPage');
    var nextPageBtn = document.getElementById('nextPage');
    var docNameEl = document.getElementById('signerDocName');

    var signForm = document.getElementById('signForm');
    var signBtn = document.getElementById('signBtn');
    var placementStatus = document.getElementById('placementStatus');
    var dateTimeInput = document.getElementById('signerDateTime');

    var progressSection = document.getElementById('signerProgress');
    var progressFill = document.getElementById('signerProgressFill');
    var progressText = document.getElementById('signerProgressText');

    var downloadSection = document.getElementById('signerDownload');
    var downloadBtn = document.getElementById('signerDownloadBtn');
    var verifyLink = document.getElementById('signerVerifyLink');
    var sigIdEl = document.getElementById('signerSigId');

    var errorSection = document.getElementById('signerError');
    var errorMsg = document.getElementById('signerErrorMsg');

    if (!uploadZone) return;

    // ─── STATE ───────────────────────────────────────────────────────
    var pages = [];
    var currentPage = 0;
    var filePath = '';
    var originalName = '';
    var signatureX = 0;
    var signatureY = 0;
    var signaturePlaced = false;

    // ─── DATE/TIME UPDATER ───────────────────────────────────────────
    function updateDateTime() {
        if (dateTimeInput) {
            var now = new Date();
            dateTimeInput.value = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
    }
    updateDateTime();
    setInterval(updateDateTime, 1000);

    // ─── FILE UPLOAD ─────────────────────────────────────────────────
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
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', function () {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    function handleFile(file) {
        var validTypes = ['.pdf', '.docx', '.doc'];
        var ext = '.' + file.name.split('.').pop().toLowerCase();
        if (validTypes.indexOf(ext) === -1) {
            alert('Please upload a PDF or Word document.');
            return;
        }

        originalName = file.name;
        docNameEl.textContent = file.name;

        // Upload for preview
        var formData = new FormData();
        formData.append('file', file);
        formData.append('csrfmiddlewaretoken', config.csrfToken);

        uploadSection.classList.add('d-none');
        signerInterface.classList.remove('d-none');
        previewLoading.classList.remove('d-none');
        previewImage.classList.add('d-none');

        fetch('/doc-signer/preview/', {
            method: 'POST',
            body: formData,
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                pages = data.pages;
                filePath = data.file_path;
                originalName = data.original_name || originalName;

                document.getElementById('signerFilePath').value = filePath;
                document.getElementById('signerOriginalName').value = originalName;

                currentPage = 0;
                showPage(0);
                updatePageNav();
            } else {
                showSignerError(data.error || 'Failed to load preview.');
            }
        })
        .catch(function (err) {
            showSignerError('Failed to upload document: ' + err.message);
        });
    }

    // ─── PAGE NAVIGATION ─────────────────────────────────────────────
    function showPage(idx) {
        if (idx < 0 || idx >= pages.length) return;
        currentPage = idx;

        previewLoading.classList.add('d-none');
        previewImage.classList.remove('d-none');
        previewImage.src = pages[idx].url;

        document.getElementById('signerPageNum').value = pages[idx].page_num;
        pageIndicator.textContent = 'Page ' + pages[idx].page_num + ' / ' + pages.length;

        // Reset signature marker on page change
        signatureMarker.classList.add('d-none');
        signaturePlaced = false;
        updateSignBtn();
        updatePlacementStatus();
    }

    function updatePageNav() {
        prevPageBtn.disabled = currentPage <= 0;
        nextPageBtn.disabled = currentPage >= pages.length - 1;
    }

    prevPageBtn.addEventListener('click', function () {
        if (currentPage > 0) {
            showPage(currentPage - 1);
            updatePageNav();
        }
    });

    nextPageBtn.addEventListener('click', function () {
        if (currentPage < pages.length - 1) {
            showPage(currentPage + 1);
            updatePageNav();
        }
    });

    // ─── SIGNATURE PLACEMENT (CLICK ON PREVIEW) ─────────────────────
    previewContainer.addEventListener('click', function (e) {
        if (e.target !== previewImage) return;

        var rect = previewImage.getBoundingClientRect();
        var clickX = e.clientX - rect.left;
        var clickY = e.clientY - rect.top;

        // Scale to actual document coordinates
        var scaleX = (pages[currentPage].width || 612) / rect.width;
        var scaleY = (pages[currentPage].height || 792) / rect.height;

        signatureX = clickX * scaleX;
        signatureY = clickY * scaleY;

        document.getElementById('signerPosX').value = signatureX.toFixed(1);
        document.getElementById('signerPosY').value = signatureY.toFixed(1);

        // Show marker at click position
        signatureMarker.classList.remove('d-none');
        signatureMarker.style.left = clickX + 'px';
        signatureMarker.style.top = clickY + 'px';

        signaturePlaced = true;
        updateSignBtn();
        updatePlacementStatus();
    });

    function updatePlacementStatus() {
        if (signaturePlaced) {
            placementStatus.innerHTML =
                '<i class="fas fa-check-circle text-success me-1"></i>' +
                '<span class="text-success fw-semibold">Signature position set on Page ' +
                pages[currentPage].page_num + '</span>';
        } else {
            placementStatus.innerHTML =
                '<i class="fas fa-exclamation-circle text-warning me-1"></i>' +
                '<span class="text-muted">Click on the document to place your signature</span>';
        }
    }

    function updateSignBtn() {
        var nameOk = document.getElementById('signerName').value.trim().length > 0;
        var emailOk = document.getElementById('signerEmail').value.trim().indexOf('@') > -1;
        signBtn.disabled = !(signaturePlaced && nameOk && emailOk);
    }

    // Update sign button state on input changes
    var signerName = document.getElementById('signerName');
    var signerEmail = document.getElementById('signerEmail');
    if (signerName) signerName.addEventListener('input', updateSignBtn);
    if (signerEmail) signerEmail.addEventListener('input', updateSignBtn);

    // Password toggle
    var toggleSignerPw = document.getElementById('toggleSignerPw');
    var signerPassword = document.getElementById('signerPassword');
    if (toggleSignerPw && signerPassword) {
        toggleSignerPw.addEventListener('click', function () {
            var type = signerPassword.type === 'password' ? 'text' : 'password';
            signerPassword.type = type;
            toggleSignerPw.querySelector('i').classList.toggle('fa-eye');
            toggleSignerPw.querySelector('i').classList.toggle('fa-eye-slash');
        });
    }

    // ─── SIGN DOCUMENT ───────────────────────────────────────────────
    signForm.addEventListener('submit', function (e) {
        e.preventDefault();

        if (!signaturePlaced) {
            alert('Please click on the document to place your signature first.');
            return;
        }

        // Check if anonymous user needs email
        if (!config.isAuthenticated && !config.hasEmail) {
            var emailModal = document.getElementById('emailModal');
            if (emailModal) {
                var modal = new bootstrap.Modal(emailModal);
                modal.show();
            }
            return;
        }

        var formData = new FormData(signForm);

        // Show progress
        signerInterface.classList.add('d-none');
        progressSection.classList.remove('d-none');
        progressSection.classList.add('slide-up');

        animateSignerProgress();

        fetch('/doc-signer/sign/', {
            method: 'POST',
            body: formData,
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            clearInterval(signerProgressInterval);

            if (data.need_email) {
                progressSection.classList.add('d-none');
                signerInterface.classList.remove('d-none');
                var emailModal = document.getElementById('emailModal');
                if (emailModal) {
                    var modal = new bootstrap.Modal(emailModal);
                    modal.show();
                }
                return;
            }

            if (data.limit_reached) {
                progressSection.classList.add('d-none');
                var limitModal = document.getElementById('limitModal');
                var limitMessage = document.getElementById('limitMessage');
                if (limitModal && limitMessage) {
                    limitMessage.textContent = data.error;
                    var modal = new bootstrap.Modal(limitModal);
                    modal.show();
                }
                resetSigner();
                return;
            }

            if (data.success) {
                progressFill.style.width = '100%';
                progressText.textContent = 'Signed!';
                setTimeout(function () {
                    showSignerDownload(data);
                }, 500);
            } else {
                showSignerError(data.error || 'Signing failed.');
            }
        })
        .catch(function (err) {
            clearInterval(signerProgressInterval);
            showSignerError('Network error: ' + err.message);
        });
    });

    // ─── PROGRESS ────────────────────────────────────────────────────
    var signerProgressInterval;

    function animateSignerProgress() {
        var width = 0;
        progressFill.style.width = '0%';
        progressText.textContent = 'Applying signature...';

        signerProgressInterval = setInterval(function () {
            if (width < 85) {
                width += Math.random() * 6 + 2;
                if (width > 85) width = 85;
                progressFill.style.width = width + '%';
            }
            if (width < 30) {
                progressText.textContent = 'Processing document...';
            } else if (width < 60) {
                progressText.textContent = 'Applying electronic signature...';
            } else {
                progressText.textContent = 'Computing integrity hash...';
            }
        }, 300);
    }

    // ─── DOWNLOAD ────────────────────────────────────────────────────
    function showSignerDownload(data) {
        progressSection.classList.add('d-none');
        downloadSection.classList.remove('d-none');
        downloadSection.classList.add('slide-up');

        downloadBtn.href = data.download_url;
        if (data.signature_id) {
            sigIdEl.textContent = 'Signature ID: ' + data.signature_id;
        }
        if (data.verify_url) {
            verifyLink.href = data.verify_url;
        }
    }

    // ─── ERROR ───────────────────────────────────────────────────────
    function showSignerError(msg) {
        clearInterval(signerProgressInterval);
        progressSection.classList.add('d-none');
        signerInterface.classList.add('d-none');
        errorSection.classList.remove('d-none');
        errorSection.classList.add('slide-up');
        errorMsg.textContent = msg;
    }

    // ─── RESET ───────────────────────────────────────────────────────
    function resetSigner() {
        pages = [];
        currentPage = 0;
        filePath = '';
        originalName = '';
        signatureX = 0;
        signatureY = 0;
        signaturePlaced = false;
        fileInput.value = '';

        signForm.reset();
        updateDateTime();

        uploadSection.classList.remove('d-none');
        signerInterface.classList.add('d-none');
        progressSection.classList.add('d-none');
        downloadSection.classList.add('d-none');
        errorSection.classList.add('d-none');
        signatureMarker.classList.add('d-none');

        signBtn.disabled = true;
        updatePlacementStatus();
    }

    // Reset buttons
    var startOverBtn = document.getElementById('signerStartOver');
    var newDocBtn = document.getElementById('signerNewDoc');
    var retryBtn = document.getElementById('signerRetry');

    if (startOverBtn) startOverBtn.addEventListener('click', resetSigner);
    if (newDocBtn) newDocBtn.addEventListener('click', resetSigner);
    if (retryBtn) retryBtn.addEventListener('click', resetSigner);
});
