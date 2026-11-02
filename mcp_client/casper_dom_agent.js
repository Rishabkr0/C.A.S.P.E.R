/**
 * CASPER DOM Agent & Ghost Cursor Engine
 * Injected into Chrome tabs to provide:
 * 1. Set-of-Marks interactive element detection with numeric badges
 * 2. Visual Ghost Cursor with smooth Bézier glide and click ripple animations
 * 3. Human-like interaction (click, type, hover, scroll)
 */

(function () {
  if (window.__casperAgent) {
    return; // Already initialized
  }

  class CasperDOMAgent {
    constructor() {
      this.elementsMap = new Map();
      this.cursor = null;
      this.badgeContainer = null;
      this.currentX = window.innerWidth / 2;
      this.currentY = window.innerHeight / 2;
      this.isMoving = false;
      this.initOverlay();
    }

    initOverlay() {
      // 1. Root Container
      let host = document.getElementById("__casper_overlay_root__");
      if (!host) {
        host = document.createElement("div");
        host.id = "__casper_overlay_root__";
        host.style.cssText = "all: initial; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 2147483640;";
        document.documentElement.appendChild(host);
      }

      // 2. Inject CSS Styles
      let style = document.getElementById("__casper_styles__");
      if (!style) {
        style = document.createElement("style");
        style.id = "__casper_styles__";
        style.textContent = `
          .casper-ghost-cursor {
            position: fixed;
            width: 28px;
            height: 28px;
            pointer-events: none;
            z-index: 2147483647;
            transform: translate(-3px, -2px);
            transition: left 0.38s cubic-bezier(0.22, 1, 0.36, 1), top 0.38s cubic-bezier(0.22, 1, 0.36, 1);
            filter: drop-shadow(0 0 10px rgba(0, 229, 255, 0.85)) drop-shadow(0 2px 4px rgba(0,0,0,0.5));
          }
          .casper-ghost-cursor svg {
            width: 100%;
            height: 100%;
          }
          .casper-cursor-label {
            position: absolute;
            left: 24px;
            top: 14px;
            background: rgba(10, 20, 35, 0.9);
            color: #00e5ff;
            border: 1px solid rgba(0, 229, 255, 0.6);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 4px;
            white-space: nowrap;
            box-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
            opacity: 0;
            transition: opacity 0.2s ease;
          }
          .casper-click-ripple {
            position: fixed;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: 2px solid #00e5ff;
            background: rgba(0, 229, 255, 0.3);
            pointer-events: none;
            z-index: 2147483646;
            transform: translate(-50%, -50%) scale(0.2);
            animation: casper_ripple_anim 0.55s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
          }
          @keyframes casper_ripple_anim {
            0% {
              transform: translate(-50%, -50%) scale(0.2);
              opacity: 1;
              box-shadow: 0 0 12px #00e5ff;
            }
            100% {
              transform: translate(-50%, -50%) scale(3.5);
              opacity: 0;
              box-shadow: 0 0 2px #00e5ff;
            }
          }
          .casper-som-badge {
            position: absolute;
            background: linear-gradient(135deg, #00e5ff 0%, #0099ff 100%);
            color: #050e1a;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            font-size: 11px;
            font-weight: 800;
            padding: 1px 6px;
            border-radius: 4px;
            pointer-events: none;
            z-index: 2147483645;
            box-shadow: 0 0 8px rgba(0, 229, 255, 0.7), 0 2px 4px rgba(0,0,0,0.6);
            border: 1px solid #ffffff;
            transform: translateY(-50%);
            white-space: nowrap;
          }
          .casper-som-highlight {
            outline: 2px solid #00e5ff !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.4) !important;
          }
        `;
        document.documentElement.appendChild(style);
      }

      // 3. Ghost Cursor Element
      let cursor = document.getElementById("__casper_cursor__");
      if (!cursor) {
        cursor = document.createElement("div");
        cursor.id = "__casper_cursor__";
        cursor.className = "casper-ghost-cursor";
        cursor.style.left = `${this.currentX}px`;
        cursor.style.top = `${this.currentY}px`;
        cursor.innerHTML = `
          <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 3L12 23L16 14.5L24.5 10.5L4 3Z" fill="#00e5ff" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
            <circle cx="15.5" cy="14.5" r="2" fill="#ffffff"/>
          </svg>
          <div class="casper-cursor-label" id="__casper_cursor_label__">CASPER</div>
        `;
        host.appendChild(cursor);
      }
      this.cursor = cursor;

      // 4. Badges Container
      let badges = document.getElementById("__casper_badges__");
      if (!badges) {
        badges = document.createElement("div");
        badges.id = "__casper_badges__";
        host.appendChild(badges);
      }
      this.badgeContainer = badges;
    }

    setCursorLabel(text) {
      const label = document.getElementById("__casper_cursor_label__");
      if (label) {
        if (text) {
          label.textContent = text;
          label.style.opacity = "1";
        } else {
          label.style.opacity = "0";
        }
      }
    }

    async moveCursorTo(x, y, label = null) {
      this.initOverlay();
      this.setCursorLabel(label);
      this.cursor.style.left = `${x}px`;
      this.cursor.style.top = `${y}px`;
      this.currentX = x;
      this.currentY = y;
      // Wait for CSS glide transition to finish
      await new Promise(r => setTimeout(r, 400));
    }

    playClickEffect(x, y) {
      const ripple = document.createElement("div");
      ripple.className = "casper-click-ripple";
      ripple.style.left = `${x}px`;
      ripple.style.top = `${y}px`;
      document.getElementById("__casper_overlay_root__").appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    }

    clearBadges() {
      if (this.badgeContainer) {
        this.badgeContainer.innerHTML = "";
      }
      document.querySelectorAll(".casper-som-highlight").forEach(el => {
        el.classList.remove("casper-som-highlight");
      });
      this.setCursorLabel(null);
    }

    /**
     * Scan the page for interactive elements and optionally render Set-of-Marks badges.
     */
    scanInteractiveElements(options = { showBadges: false, maxElements: 75 }) {
      this.initOverlay();
      this.clearBadges();
      this.elementsMap.clear();

      const candidates = Array.from(document.querySelectorAll(
        "a[href], button, input, textarea, select, details, summary, " +
        "[role='button'], [role='link'], [role='checkbox'], [role='radio'], " +
        "[role='tab'], [role='menuitem'], [role='searchbox'], [role='switch'], " +
        "[tabindex]:not([tabindex='-1']), [onclick]"
      ));

      // Also detect elements with CSS cursor: pointer
      const allDivsSpans = document.querySelectorAll("div, span, li, p");
      for (let i = 0; i < Math.min(allDivsSpans.length, 300); i++) {
        const el = allDivsSpans[i];
        if (!candidates.includes(el)) {
          const style = window.getComputedStyle(el);
          if (style.cursor === "pointer" && el.children.length <= 2) {
            candidates.push(el);
          }
        }
      }

      const results = [];
      let index = 1;

      for (const el of candidates) {
        if (index > options.maxElements) break;

        // Skip children if parent button/link is already captured
        const parentCandidate = el.parentElement ? el.parentElement.closest("button, a[href]") : null;
        if (parentCandidate && parentCandidate !== el && candidates.includes(parentCandidate)) {
          continue;
        }

        const rect = el.getBoundingClientRect();
        // Check visibility in viewport
        if (rect.width < 6 || rect.height < 6) continue;
        if (
          rect.bottom <= 0 ||
          rect.top >= window.innerHeight ||
          rect.right <= 0 ||
          rect.left >= window.innerWidth
        ) {
          continue;
        }

        const style = window.getComputedStyle(el);
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          parseFloat(style.opacity) < 0.1 ||
          style.pointerEvents === "none"
        ) {
          continue;
        }

        // Extract semantic text label
        let label = (
          el.getAttribute("aria-label") ||
          el.innerText ||
          el.placeholder ||
          el.title ||
          el.value ||
          el.getAttribute("name") ||
          el.getAttribute("id") ||
          ""
        ).trim().replace(/\s+/g, " ");

        // Truncate long labels
        if (label.length > 50) label = label.slice(0, 47) + "...";

        // Determine tag/type
        let role = el.getAttribute("role") || el.tagName.toLowerCase();
        if (el.tagName.toLowerCase() === "input") {
          role = `input:${el.type || "text"}`;
        }

        const centerX = Math.round(rect.left + rect.width / 2);
        const centerY = Math.round(rect.top + rect.height / 2);

        const item = {
          id: index,
          role: role,
          label: label || `[${role}]`,
          x: centerX,
          y: centerY,
          rect: {
            top: Math.round(rect.top),
            left: Math.round(rect.left),
            width: Math.round(rect.width),
            height: Math.round(rect.height)
          }
        };

        this.elementsMap.set(index, el);
        results.push(item);

        // Render badge
        if (options.showBadges && this.badgeContainer) {
          const badge = document.createElement("div");
          badge.className = "casper-som-badge";
          badge.textContent = `${index}`;
          // Position at top-left of the element
          const badgeTop = Math.max(4, rect.top + window.scrollY);
          const badgeLeft = Math.max(4, rect.left + window.scrollX);
          badge.style.top = `${badgeTop}px`;
          badge.style.left = `${badgeLeft}px`;
          this.badgeContainer.appendChild(badge);
        }

        index++;
      }

      return results;
    }

    /**
     * Interactively click an element by its Set-of-Marks ID
     */
    async clickElementById(id) {
      this.initOverlay();
      const el = this.elementsMap.get(Number(id));
      if (!el) {
        return { success: false, error: `Element with ID ${id} not found. Try scanning the page first.` };
      }

      // 1. Scroll into view if needed
      el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
      await new Promise(r => setTimeout(r, 250));

      const rect = el.getBoundingClientRect();
      const x = Math.round(rect.left + rect.width / 2);
      const y = Math.round(rect.top + rect.height / 2);

      // 2. Glide Casper Ghost Cursor to element
      await this.moveCursorTo(x, y, "Clicking...");

      // 3. Highlight element briefly
      el.classList.add("casper-som-highlight");
      this.playClickEffect(x, y);

      // 4. Dispatch standard browser mouse events for framework compatibility
      el.focus();
      const mousedown = new MouseEvent("mousedown", { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window });
      const mouseup = new MouseEvent("mouseup", { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window });
      const click = new MouseEvent("click", { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window });

      el.dispatchEvent(mousedown);
      el.dispatchEvent(mouseup);
      el.click();
      el.dispatchEvent(click);

      setTimeout(() => {
        el.classList.remove("casper-som-highlight");
        this.setCursorLabel(null);
      }, 500);

      return {
        success: true,
        id: id,
        x: x,
        y: y,
        label: el.innerText || el.getAttribute("aria-label") || el.tagName
      };
    }

    /**
     * Type text into an element by its ID
     */
    async typeElementById(id, text, clearFirst = true) {
      this.initOverlay();
      const el = this.elementsMap.get(Number(id));
      if (!el) {
        return { success: false, error: `Element with ID ${id} not found.` };
      }

      el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
      await new Promise(r => setTimeout(r, 200));

      const rect = el.getBoundingClientRect();
      const x = Math.round(rect.left + rect.width / 2);
      const y = Math.round(rect.top + rect.height / 2);

      await this.moveCursorTo(x, y, "Typing...");
      this.playClickEffect(x, y);

      el.focus();
      if (clearFirst) {
        if ("value" in el) el.value = "";
        else if (el.isContentEditable) el.textContent = "";
      }

      // React / Vue property descriptor bypass
      const isInput = el instanceof HTMLInputElement;
      const isTextArea = el instanceof HTMLTextAreaElement;

      if (isInput || isTextArea) {
        const proto = isInput ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
        const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
        if (descriptor && descriptor.set) {
          descriptor.set.call(el, text);
        } else {
          el.value = text;
        }
      } else if (el.isContentEditable) {
        el.textContent = text;
      }

      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));

      setTimeout(() => this.setCursorLabel(null), 400);

      return {
        success: true,
        id: id,
        typed: text
      };
    }

    /**
     * Move cursor to arbitrary coordinates and click
     */
    async clickCoordinates(x, y) {
      this.initOverlay();
      await this.moveCursorTo(x, y, "Clicking...");
      this.playClickEffect(x, y);

      const target = document.elementFromPoint(x, y);
      if (target) {
        target.focus();
        target.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, clientX: x, clientY: y }));
        target.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, clientX: x, clientY: y }));
        target.click();
      }

      setTimeout(() => this.setCursorLabel(null), 400);
      return { success: true, x, y };
    }
  }

  window.__casperAgent = new CasperDOMAgent();
})();

