/**
 * Simon on the Streets - Quick Capture MVP
 * Core client-side functionality:
 * - Geolocation + What3Words conversion (via backend proxy)
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

          latInput.value = lat;
          lngInput.value = lng;

          convertToWhat3Words(lat, lng);
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

  function convertToWhat3Words(lat, lng) {
    showLocationStatus("Converting to What3Words...", false);

    fetch("/location/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: lat, lng: lng }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.words) {
          locationInput.value = data.words;
          showLocationStatus("Location: ///" + data.words, false);
        } else {
          locationInput.value = lat.toFixed(5) + "," + lng.toFixed(5);
          showLocationStatus(
            data.error || "W3W conversion unavailable, coordinates saved.",
            true
          );
        }
      })
      .catch(function () {
        locationInput.value = lat.toFixed(5) + "," + lng.toFixed(5);
        showLocationStatus("W3W conversion failed, coordinates saved.", true);
      })
      .finally(function () {
        if (shareBtn) shareBtn.disabled = false;
      });
  }

  function showLocationStatus(message, isError) {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.classList.remove("hidden", "text-red-500", "text-gray-500");
    locationStatus.classList.add(isError ? "text-red-500" : "text-gray-500");
  }
})();
