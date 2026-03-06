document.addEventListener('DOMContentLoaded', function () {
    var config = window.PDFTOOLS_CONFIG || {};

    // ─── DOM ELEMENTS ────────────────────────────────────────────────
    var uploadSection = document.getElementById('uploadSection');
    var uploadZone = document.getElementById('extractUploadZone');
    var fileInput = document.getElementById('extractFileInput');
    var selectBtn = document.getElementById('extractSelectBtn');
    var progressSection = document.getElementById('extractProgress');
    var progressFill = document.getElementById('extractProgressFill');
    var progressText = document.getElementById('extractProgressText');
    var resultsSection = document.getElementById('extractResults');
    var errorSection = document.getElementById('extractError');
    var errorMsg = document.getElementById('extractErrorMsg');
    var startOverBtn = document.getElementById('extractStartOver');
    var tryAgainBtn = document.getElementById('extractTryAgain');
    var cancelBtn = document.getElementById('cancelExtract');
    var downloadBtn = document.getElementById('downloadBtn');
    var downloadFormat = document.getElementById('downloadFormat');

    // PDF preview
    var pdfPageImg = document.getElementById('pdfPageImg');
    var prevPageBtn = document.getElementById('prevPage');
    var nextPageBtn = document.getElementById('nextPage');
    var currentPageNum = document.getElementById('currentPageNum');
    var totalPageNum = document.getElementById('totalPageNum');
    var zoomInBtn = document.getElementById('zoomIn');
    var zoomOutBtn = document.getElementById('zoomOut');
    var zoomLevelEl = document.getElementById('zoomLevel');
    var previewFileName = document.getElementById('previewFileName');
    var previewFileSize = document.getElementById('previewFileSize');

    if (!uploadZone) return;

    // ─── STATE ──────────────────────────────────────────────────────
    var selectedFile = null;
    var extractionData = null; // Full extraction result from server
    var pageImages = [];       // Array of page image URLs
    var currentPage = 1;
    var totalPages = 0;
    var zoomLevel = 100;
    var downloadUrls = {};     // { excel: url, json: url, csv: url }

    // ─── FILE SELECTION ─────────────────────────────────────────────
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
        if (files.length > 0) handleFile(files[0]);
    });

    fileInput.addEventListener('change', function () {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    function handleFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('Please select a PDF file.');
            return;
        }
        selectedFile = file;

        // Check email for anonymous
        if (!config.isAuthenticated && !config.hasEmail) {
            var emailModal = document.getElementById('emailModal');
            if (emailModal) {
                var modal = new bootstrap.Modal(emailModal);
                modal.show();
                // Re-process after email submitted
                emailModal.addEventListener('hidden.bs.modal', function onHide() {
                    emailModal.removeEventListener('hidden.bs.modal', onHide);
                    if (config.hasEmail) {
                        startExtraction();
                    }
                });
            }
            return;
        }

        startExtraction();
    }

    // ─── EXTRACTION PROCESS ─────────────────────────────────────────
    function startExtraction() {
        if (!selectedFile) return;

        // Show progress
        uploadSection.classList.add('d-none');
        progressSection.classList.remove('d-none');
        progressSection.classList.add('slide-up');
        resultsSection.classList.add('d-none');
        errorSection.classList.add('d-none');

        var progressInterval = animateProgress();

        var formData = new FormData();
        formData.append('file', selectedFile);

        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/extractor-process/', true);
        xhr.setRequestHeader('X-CSRFToken', config.csrfToken);

        xhr.onload = function () {
            clearInterval(progressInterval);
            try {
                var data = JSON.parse(xhr.responseText);

                if (data.need_email) {
                    progressSection.classList.add('d-none');
                    uploadSection.classList.remove('d-none');
                    var emailModal = document.getElementById('emailModal');
                    if (emailModal) {
                        var modal = new bootstrap.Modal(emailModal);
                        modal.show();
                    }
                    return;
                }

                if (xhr.status === 200 && data.success) {
                    progressFill.style.width = '100%';
                    progressText.textContent = 'Done!';
                    setTimeout(function () {
                        showResults(data);
                    }, 400);
                } else {
                    showError(data.error || 'Extraction failed.');
                }
            } catch (err) {
                showError('Invalid server response.');
            }
        };

        xhr.onerror = function () {
            clearInterval(progressInterval);
            showError('Network error. Please try again.');
        };

        xhr.send(formData);
    }

    // ─── PROGRESS ANIMATION ─────────────────────────────────────────
    function animateProgress() {
        var width = 0;
        progressFill.style.width = '0%';

        var messages = [
            'Uploading document...',
            'Analyzing PDF structure...',
            'Extracting text content...',
            'Running OCR if needed...',
            'Parsing fields & data...',
            'Detecting line items...',
            'Generating page previews...',
            'Building results...',
        ];
        var msgIndex = 0;

        return setInterval(function () {
            if (width < 88) {
                width += Math.random() * 5 + 1;
                if (width > 88) width = 88;
                progressFill.style.width = width + '%';
            }
            if (width > msgIndex * 11 && msgIndex < messages.length) {
                progressText.textContent = messages[msgIndex];
                msgIndex++;
            }
        }, 500);
    }

    // ─── SHOW RESULTS (Split Panel) ─────────────────────────────────
    function showResults(data) {
        progressSection.classList.add('d-none');
        resultsSection.classList.remove('d-none');
        resultsSection.classList.add('slide-up');

        extractionData = data;
        pageImages = data.pages || [];
        totalPages = pageImages.length;
        currentPage = 1;
        downloadUrls = data.download_urls || {};

        // File info
        previewFileName.textContent = selectedFile.name;
        previewFileSize.textContent = formatFileSize(selectedFile.size);

        // Stats
        var info = data.extraction || {};
        document.getElementById('statPages').textContent = info.total_pages || 0;
        document.getElementById('statChars').textContent = formatNumber(info.total_characters || 0);
        document.getElementById('extractMethod').textContent = (info.extraction_method || 'text').toUpperCase();

        // Page navigation
        totalPageNum.textContent = totalPages;
        updatePageDisplay();

        // Populate extracted data panels
        populateFields(info.extracted_fields || {});
        populateKeyValues(info.extracted_fields || {});
        populateLineItems(info.extracted_fields || {});
        populateRawText(info.raw_text_preview || '');
    }

    // ─── PDF PAGE NAVIGATION ────────────────────────────────────────
    function updatePageDisplay() {
        if (totalPages === 0) return;

        currentPageNum.textContent = currentPage;
        var page = pageImages[currentPage - 1];
        if (page && page.url) {
            pdfPageImg.src = page.url;
            pdfPageImg.style.width = zoomLevel + '%';
        }

        prevPageBtn.disabled = currentPage <= 1;
        nextPageBtn.disabled = currentPage >= totalPages;
    }

    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', function () {
            if (currentPage > 1) {
                currentPage--;
                updatePageDisplay();
            }
        });
    }

    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', function () {
            if (currentPage < totalPages) {
                currentPage++;
                updatePageDisplay();
            }
        });
    }

    // Zoom
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', function () {
            if (zoomLevel < 200) {
                zoomLevel += 20;
                zoomLevelEl.textContent = zoomLevel + '%';
                pdfPageImg.style.width = zoomLevel + '%';
            }
        });
    }

    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', function () {
            if (zoomLevel > 40) {
                zoomLevel -= 20;
                zoomLevelEl.textContent = zoomLevel + '%';
                pdfPageImg.style.width = zoomLevel + '%';
            }
        });
    }

    // ─── POPULATE AUTO-DETECTED FIELDS ──────────────────────────────
    function populateFields(fields) {
        var container = document.getElementById('fieldsChecklist');
        var noMsg = document.getElementById('noFieldsMsg');
        container.innerHTML = '';
        var count = 0;

        var skipKeys = ['line_items', 'all_key_value_pairs'];

        for (var key in fields) {
            if (skipKeys.indexOf(key) !== -1) continue;
            count++;
            var displayKey = key.replace(/_/g, ' ').replace(/\b\w/g, function (l) {
                return l.toUpperCase();
            });
            var val = String(fields[key]);

            var row = document.createElement('div');
            row.className = 'field-row';
            row.innerHTML =
                '<label class="field-check">' +
                    '<input type="checkbox" checked data-field="' + escapeHtml(key) + '"> ' +
                    '<span class="field-key">' + escapeHtml(displayKey) + '</span>' +
                '</label>' +
                '<span class="field-value">' + escapeHtml(val) + '</span>';
            container.appendChild(row);
        }

        document.getElementById('statFieldsBadge').textContent = count + ' field' + (count !== 1 ? 's' : '');

        if (count === 0) {
            noMsg.classList.remove('d-none');
        } else {
            noMsg.classList.add('d-none');
        }
    }

    // ─── POPULATE KEY-VALUE PAIRS ───────────────────────────────────
    function populateKeyValues(fields) {
        var container = document.getElementById('kvList');
        var noMsg = document.getElementById('noKvMsg');
        container.innerHTML = '';
        var kvPairs = fields.all_key_value_pairs || {};
        var count = 0;

        for (var k in kvPairs) {
            count++;
            var displayKey = k.replace(/_/g, ' ').replace(/\b\w/g, function (l) {
                return l.toUpperCase();
            });
            var row = document.createElement('div');
            row.className = 'kv-row';
            row.innerHTML =
                '<label class="field-check">' +
                    '<input type="checkbox" checked data-kv="' + escapeHtml(k) + '"> ' +
                    '<span class="field-key">' + escapeHtml(displayKey) + '</span>' +
                '</label>' +
                '<span class="field-value">' + escapeHtml(String(kvPairs[k])) + '</span>';
            container.appendChild(row);
        }

        if (count === 0) {
            noMsg.classList.remove('d-none');
        } else {
            noMsg.classList.add('d-none');
        }
    }

    // ─── POPULATE LINE ITEMS ────────────────────────────────────────
    function populateLineItems(fields) {
        var tbody = document.getElementById('lineItemsBody');
        var noMsg = document.getElementById('noItemsMsg');
        var tableEl = document.getElementById('lineItemsTable');
        tbody.innerHTML = '';
        var items = fields.line_items || [];

        document.getElementById('statItemsBadge').textContent = items.length + ' item' + (items.length !== 1 ? 's' : '');

        if (items.length === 0) {
            noMsg.classList.remove('d-none');
            tableEl.classList.add('d-none');
            return;
        }

        noMsg.classList.add('d-none');
        tableEl.classList.remove('d-none');

        items.forEach(function (item, idx) {
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><input type="checkbox" checked data-item="' + idx + '"></td>' +
                '<td>' + escapeHtml(item.description || '') + '</td>' +
                '<td>' + escapeHtml(item.value_1 || '') + '</td>' +
                '<td>' + escapeHtml(item.value_2 || '') + '</td>' +
                '<td>' + escapeHtml(item.value_3 || '') + '</td>';
            tbody.appendChild(tr);
        });
    }

    // Select all line items toggle
    var selectAllItems = document.getElementById('selectAllItems');
    if (selectAllItems) {
        selectAllItems.addEventListener('change', function () {
            var checkboxes = document.querySelectorAll('#lineItemsBody input[type="checkbox"]');
            checkboxes.forEach(function (cb) {
                cb.checked = selectAllItems.checked;
            });
        });
    }

    // ─── POPULATE RAW TEXT ──────────────────────────────────────────
    function populateRawText(text) {
        var el = document.getElementById('rawTextPreview');
        el.textContent = text || '(No text extracted)';
    }

    // ─── TAB SWITCHING ──────────────────────────────────────────────
    document.querySelectorAll('.data-tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            // Deactivate all tabs
            document.querySelectorAll('.data-tab').forEach(function (t) {
                t.classList.remove('active');
            });
            document.querySelectorAll('.data-tab-content').forEach(function (c) {
                c.classList.remove('active');
            });

            // Activate clicked tab
            tab.classList.add('active');
            var tabName = tab.dataset.tab;
            var contentMap = {
                'fields': 'tabFields',
                'keyvalue': 'tabKeyValue',
                'lineitems': 'tabLineItems',
                'rawtext': 'tabRawText',
            };
            var content = document.getElementById(contentMap[tabName]);
            if (content) content.classList.add('active');
        });
    });

    // ─── DOWNLOAD ───────────────────────────────────────────────────
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            var fmt = downloadFormat.value;
            if (downloadUrls[fmt]) {
                // Already have the file
                window.location.href = downloadUrls[fmt];
            } else {
                // Generate the download for selected format
                downloadBtn.disabled = true;
                downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating...';

                var formData = new FormData();
                formData.append('file', selectedFile);
                formData.append('output_format', fmt);

                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/extract-data/', true);
                xhr.setRequestHeader('X-CSRFToken', config.csrfToken);

                xhr.onload = function () {
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i class="fas fa-download me-1"></i>Download';
                    try {
                        var data = JSON.parse(xhr.responseText);
                        if (data.success && data.download_url) {
                            downloadUrls[fmt] = data.download_url;
                            window.location.href = data.download_url;
                        } else {
                            alert(data.error || 'Download failed.');
                        }
                    } catch (e) {
                        alert('Download failed. Please try again.');
                    }
                };

                xhr.onerror = function () {
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i class="fas fa-download me-1"></i>Download';
                    alert('Network error.');
                };

                xhr.send(formData);
            }
        });
    }

    // ─── ERROR ──────────────────────────────────────────────────────
    function showError(msg) {
        progressSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        errorSection.classList.remove('d-none');
        errorSection.classList.add('slide-up');
        errorMsg.textContent = msg;
    }

    // ─── RESET ──────────────────────────────────────────────────────
    function resetAll() {
        selectedFile = null;
        extractionData = null;
        pageImages = [];
        downloadUrls = {};
        currentPage = 1;
        totalPages = 0;
        zoomLevel = 100;
        fileInput.value = '';

        uploadSection.classList.remove('d-none');
        progressSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        errorSection.classList.add('d-none');

        if (zoomLevelEl) zoomLevelEl.textContent = '100%';
        if (pdfPageImg) pdfPageImg.style.width = '100%';
    }

    if (startOverBtn) startOverBtn.addEventListener('click', resetAll);
    if (tryAgainBtn) tryAgainBtn.addEventListener('click', resetAll);
    if (cancelBtn) cancelBtn.addEventListener('click', resetAll);

    // ─── UTILITIES ──────────────────────────────────────────────────
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num;
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
});
