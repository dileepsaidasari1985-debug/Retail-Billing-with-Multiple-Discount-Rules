/* ==========================================================================
   NovaMart Smart Retail Billing System - Client Interactions
   Handles accessible mobile navigation drawer, delete confirmation <dialog>,
   and non-intrusive form UX enhancements.
   ========================================================================== */

(function () {
  "use strict";

  // ------------------------------------------------------------------------
  // 1. Mobile Navigation Drawer (native modal <dialog> + scroll-snap)
  // ------------------------------------------------------------------------
  const drawer = document.getElementById("mobile-drawer");
  const openBtn = document.getElementById("drawer-open");
  const closeBtn = document.getElementById("drawer-close");

  if (drawer && openBtn && closeBtn) {
    const scroller = drawer.querySelector(".Drawer-scroller");
    const sheet = drawer.querySelector(".Drawer-sheet");

    async function openDrawer() {
      drawer.showModal();
      if (!CSS.supports("scroll-initial-target", "nearest")) {
        scroller.scrollTo({ left: scroller.offsetWidth, behavior: "instant" });
        await new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve))
        );
      }
      scroller.scrollTo({ left: 0, behavior: "auto" });
    }

    function closeDrawer() {
      scroller.scrollTo({ left: scroller.offsetWidth, behavior: "auto" });
    }

    function onDrawerOpened() {
      openBtn.setAttribute("aria-expanded", "true");
    }

    function onDrawerClosed() {
      if (drawer.open) {
        drawer.close();
      }
      openBtn.setAttribute("aria-expanded", "false");
    }

    if (!CSS.supports("animation-timeline: scroll()")) {
      scroller.addEventListener("scroll", () => {
        if (sheet.offsetWidth > 0) {
          const ratio = Math.max(0, Math.min(1, 1 - scroller.scrollLeft / sheet.offsetWidth));
          drawer.style.setProperty("--drawer-backdrop", String(ratio));
        }
      });
    }

    const visibleThreshold = 1 / Math.max(window.innerWidth, 320);
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (!entry) return;
        if (entry.intersectionRatio < visibleThreshold) {
          onDrawerClosed();
        } else if (entry.intersectionRatio >= 0.99) {
          onDrawerOpened();
        }
      },
      { root: drawer, threshold: [visibleThreshold, 1] }
    );
    observer.observe(sheet);

    openBtn.addEventListener("click", openDrawer);
    closeBtn.addEventListener("click", closeDrawer);

    drawer.addEventListener("click", (event) => {
      if (!sheet.contains(event.target)) {
        closeDrawer();
      }
    });

    drawer.addEventListener("cancel", (event) => {
      if (event.cancelable) {
        event.preventDefault();
        closeDrawer();
      }
    });
  }

  // ------------------------------------------------------------------------
  // 2. Delete Confirmation Modal (<dialog>) for Products
  // ------------------------------------------------------------------------
  const deleteDialog = document.getElementById("delete-confirm-dialog");
  if (deleteDialog) {
    const itemNameEl = document.getElementById("delete-item-name");
    const deleteForm = document.getElementById("delete-confirm-form");
    const cancelBtn = document.getElementById("delete-cancel-btn");

    document.querySelectorAll("[data-delete-url]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetUrl = btn.getAttribute("data-delete-url");
        const targetLabel = btn.getAttribute("data-delete-label") || "this product";
        if (deleteForm && targetUrl) {
          deleteForm.setAttribute("action", targetUrl);
        }
        if (itemNameEl) {
          itemNameEl.textContent = targetLabel;
        }
        deleteDialog.showModal();
      });
    });

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        deleteDialog.close("cancel");
      });
    }

    // Light dismiss fallback when browser lacks closedby="any"
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      let pressedOutside = false;
      const isOutside = (e) => {
        const r = deleteDialog.getBoundingClientRect();
        return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      };
      deleteDialog.addEventListener("pointerdown", (e) => {
        pressedOutside = isOutside(e);
      });
      deleteDialog.addEventListener("pointerup", (e) => {
        if (pressedOutside && isOutside(e)) {
          deleteDialog.close("cancel");
        }
      });
    }

    deleteDialog.addEventListener("close", () => {
      deleteDialog.returnValue = "";
    });
  }

  // ------------------------------------------------------------------------
  // 3. Print Invoice Buttons (CSP-friendly without inline onclick)
  // ------------------------------------------------------------------------
  document.querySelectorAll("[data-print-invoice]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.print();
    });
  });

  // ------------------------------------------------------------------------
  // 4. Live Cash Change Preview & Payment Mode Toggle
  // ------------------------------------------------------------------------
  const cashPanel = document.getElementById("cash-tendered-panel");
  const cashInput = document.getElementById("cash_tendered");
  const changeOut = document.getElementById("cash-change-output");
  const payRadios = document.querySelectorAll('input[name="payment_mode"]');

  function refreshCashUI() {
    if (!cashPanel) return;
    const selected = document.querySelector('input[name="payment_mode"]:checked');
    const isCash = !selected || selected.value === "Cash";
    cashPanel.hidden = !isCash;
    if (!isCash && cashInput) {
      cashInput.value = "";
      if (changeOut) changeOut.textContent = "";
    }
  }

  if (payRadios.length > 0) {
    payRadios.forEach((radio) => radio.addEventListener("change", refreshCashUI));
    refreshCashUI();
  }

  if (cashInput && changeOut) {
    const payable = parseFloat(cashInput.getAttribute("data-payable") || "0");
    cashInput.addEventListener("input", () => {
      const val = parseFloat(cashInput.value);
      if (Number.isNaN(val) || cashInput.value.trim() === "") {
        changeOut.textContent = "";
        changeOut.style.color = "";
        return;
      }
      const diff = val - payable;
      if (diff < 0) {
        changeOut.textContent = `Short by ₹${Math.abs(diff).toFixed(2)}`;
        changeOut.style.color = "#dc2626";
      } else {
        changeOut.textContent = `Change to return: ₹${diff.toFixed(2)}`;
        changeOut.style.color = "#15803d";
      }
    });
  }

  // ------------------------------------------------------------------------
  // 5. Prevent double-click checkout submission
  // ------------------------------------------------------------------------
  const checkoutForm = document.getElementById("checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", () => {
      const submitBtn = checkoutForm.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Generating Invoice...";
      }
    });
  }
})();
