/**
 * Simon on the Streets - Quick Capture MVP
 * Core client-side functionality:
 * - Geolocation capture (GPS coordinates stored directly)
 * - What3Words autosuggest for manual address entry
 * - Flash message auto-dismiss
 */

(function () {
  "use strict";

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
      headers: { "Content-Type": "application/json" },
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
