/**
 * Simon on the Streets - Quick Capture MVP
 * Core client-side functionality:
 * - Geolocation capture (GPS coordinates stored directly)
 * - What3Words autosuggest for manual address entry
 * - Flash message auto-dismiss
 */

(function () {
  "use strict";

  var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute("content") : "";

  window.quickCaptureCsrfHeaders = function () {
    return csrfToken ? { "X-CSRFToken": csrfToken } : {};
  };

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(function () {});
  }

  // ─── Flash messages: auto-dismiss after 5s ───────────────────────────
  document.querySelectorAll(".flash-msg").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.3s";
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 300);
    }, 5000);
  });

  // ─── Geolocation: Share my location ──────────────────────────────────
  var shareBtn = document.getElementById("share-location-btn");
  var locationInput = document.getElementById("location_search");
  var latInput = document.getElementById("location_lat");
  var lngInput = document.getElementById("location_lng");
  var locationStatus = document.getElementById("location-status");
  var suggestionsDropdown = document.getElementById("w3w-suggestions");

  // Track the user's GPS coordinates for autosuggest focus
  var userLat = null;
  var userLng = null;

  if (shareBtn) {
    shareBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        showLocationStatus("Geolocation is not supported by your browser.", true);
        return;
      }

      showLocationStatus("Getting your location...", false);
      shareBtn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        function (position) {
          var lat = position.coords.latitude;
          var lng = position.coords.longitude;

          userLat = lat;
          userLng = lng;
          latInput.value = lat;
          lngInput.value = lng;

          shareBtn.disabled = false;
          showLocationStatus(
            "GPS captured (" + lat.toFixed(5) + ", " + lng.toFixed(5) + "). Type a what3words address or leave blank.",
            false
          );
        },
        function (error) {
          shareBtn.disabled = false;
          switch (error.code) {
            case error.PERMISSION_DENIED:
              showLocationStatus("Location permission denied.", true);
              break;
            case error.POSITION_UNAVAILABLE:
              showLocationStatus("Location unavailable.", true);
              break;
            case error.TIMEOUT:
              showLocationStatus("Location request timed out.", true);
              break;
            default:
              showLocationStatus("An unknown error occurred.", true);
          }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  }

  // ─── What3Words Autosuggest ──────────────────────────────────────────
  var debounceTimer = null;
  var DEBOUNCE_DELAY = 300;

  if (locationInput && suggestionsDropdown) {
    locationInput.addEventListener("input", function () {
      clearTimeout(debounceTimer);

      var value = locationInput.value.trim();

      // AutoSuggest requires at least two words and one char of the third
      if (!isValidPartialW3W(value)) {
        hideSuggestions();
        return;
      }

      debounceTimer = setTimeout(function () {
        fetchSuggestions(value);
      }, DEBOUNCE_DELAY);
    });

    // Hide dropdown when clicking outside
    document.addEventListener("click", function (e) {
      if (!locationInput.contains(e.target) && !suggestionsDropdown.contains(e.target)) {
        hideSuggestions();
      }
    });

    // Keyboard navigation
    locationInput.addEventListener("keydown", function (e) {
      if (suggestionsDropdown.classList.contains("hidden")) return;

      var items = suggestionsDropdown.querySelectorAll("li");
      var active = suggestionsDropdown.querySelector("li.bg-brand-50");
      var index = -1;

      if (active) {
        for (var i = 0; i < items.length; i++) {
          if (items[i] === active) { index = i; break; }
        }
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (active) active.classList.remove("bg-brand-50");
        index = (index + 1) % items.length;
        items[index].classList.add("bg-brand-50");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (active) active.classList.remove("bg-brand-50");
        index = index <= 0 ? items.length - 1 : index - 1;
        items[index].classList.add("bg-brand-50");
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (active) {
          active.click();
        }
      } else if (e.key === "Escape") {
        hideSuggestions();
      }
    });
  }

  function isValidPartialW3W(value) {
    // Must have at least: word.word.c
    var parts = value.split(".");
    if (parts.length < 3) return false;
    if (parts[0].length < 1 || parts[1].length < 1 || parts[2].length < 1) return false;
    return true;
  }

  function fetchSuggestions(input) {
    var payload = { input: input };

    // Pass GPS focus if available for better relevance
    if (userLat !== null && userLng !== null) {
      payload.focus_lat = userLat;
      payload.focus_lng = userLng;
    }

    // Clip to GB by default since Simon on the Streets operates in the UK
    payload.clip_to_country = "GB";

    fetch("/location/autosuggest", {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, window.quickCaptureCsrfHeaders()),
      body: JSON.stringify(payload),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.suggestions && data.suggestions.length > 0) {
          renderSuggestions(data.suggestions);
        } else {
          hideSuggestions();
        }
      })
      .catch(function () {
        hideSuggestions();
      });
  }

  function renderSuggestions(suggestions) {
    suggestionsDropdown.innerHTML = "";

    suggestions.forEach(function (suggestion) {
      var li = document.createElement("li");
      li.className = "px-3 py-2 cursor-pointer hover:bg-brand-50 transition-colors border-b border-gray-100 last:border-0";
      li.innerHTML =
        '<span class="block text-sm font-medium text-gray-900">/// ' + escapeHtml(suggestion.words) + "</span>" +
        '<span class="block text-xs text-gray-500">' + escapeHtml(suggestion.nearestPlace || "") + "</span>";

      li.addEventListener("click", function () {
        selectSuggestion(suggestion);
      });

      suggestionsDropdown.appendChild(li);
    });

    suggestionsDropdown.classList.remove("hidden");
  }

  function selectSuggestion(suggestion) {
    locationInput.value = suggestion.words;
    hideSuggestions();
    showLocationStatus("Location: ///" + suggestion.words + (suggestion.nearestPlace ? " (" + suggestion.nearestPlace + ")" : ""), false);
  }

  function hideSuggestions() {
    if (suggestionsDropdown) {
      suggestionsDropdown.classList.add("hidden");
      suggestionsDropdown.innerHTML = "";
    }
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  // ─── Shared helpers ──────────────────────────────────────────────────
  function showLocationStatus(message, isError) {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.classList.remove("hidden", "text-red-500", "text-gray-500");
    locationStatus.classList.add(isError ? "text-red-500" : "text-gray-500");
  }
})();

// ─── Delegated handlers (Content Security Policy) ──────────────────────
// The CSP set in app/security/headers.py pins script-src to this origin and a
// per-request nonce, which blocks inline `onclick`/`onsubmit` attributes.
// These listeners replace the two that used to be written into the markup.
(function () {
  document.addEventListener("click", function (event) {
    var dismiss = event.target.closest("[data-dismiss-flash]");
    if (dismiss && dismiss.parentElement) {
      dismiss.parentElement.remove();
    }
  });

  document.addEventListener(
    "submit",
    function (event) {
      var form = event.target;
      if (!form || !form.matches("[data-confirm]")) return;
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    },
    true
  );
})();

// ─── Case access history ───────────────────────────────────────────────
// Shows who has read this case. Deliberately available to every worker, not
// just admins: team-wide visibility is only acceptable when it is visible who
// used it. See docs/adrs/007-team-wide-case-visibility.md.
(function () {
  var button = document.getElementById("access-log-btn");
  if (!button) return;

  var list = document.getElementById("access-log-entries");
  var empty = document.getElementById("access-log-empty");

  button.addEventListener("click", function () {
    button.disabled = true;
    button.textContent = "Loading...";

    fetch("/cases/" + button.dataset.caseId + "/access-log")
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var entries = data.entries || [];
        list.innerHTML = "";

        entries.forEach(function (entry) {
          var item = document.createElement("li");
          var when = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "";
          item.textContent = entry.user + " — " + describe(entry.action) + " — " + when;
          list.appendChild(item);
        });

        list.classList.toggle("hidden", entries.length === 0);
        empty.classList.toggle("hidden", entries.length > 0);
        button.textContent = "Reload reading history";
        button.disabled = false;
      })
      .catch(function () {
        button.textContent = "Could not load history";
        button.disabled = false;
      });
  });

  function describe(action) {
    var labels = {
      viewed_case: "opened the case",
      downloaded_attachment: "downloaded a document",
      played_voice_note: "played a voice note",
      viewed_audit_trail: "read the activity history",
      exported_report: "exported the report file",
      searched: "searched",
    };
    return labels[action] || action;
  }
})();
