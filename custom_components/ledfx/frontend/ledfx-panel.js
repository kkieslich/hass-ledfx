class LedFxPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = undefined;
    this._narrow = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._render();
  }

  connectedCallback() {
    this.shadowRoot.addEventListener("click", (event) => this._handleClick(event));
    this.shadowRoot.addEventListener("change", (event) => this._handleChange(event));
    this._render();
  }

  _isLedFxEntity(stateObj) {
    if (!stateObj?.entity_id) {
      return false;
    }

    return Boolean(
      stateObj.attributes?.attribution === "Data provided by LedFx" ||
        stateObj.attributes?.ledfx_device ||
        stateObj.attributes?.ledfx_entity_type ||
        stateObj.entity_id.includes(".ledfx_")
    );
  }

  _deviceCode(stateObj) {
    if (stateObj.attributes.ledfx_device || stateObj.attributes.device) {
      return stateObj.attributes.ledfx_device || stateObj.attributes.device;
    }

    const [domain, objectId] = stateObj.entity_id.split(".");
    if (!objectId?.startsWith("ledfx_")) {
      return undefined;
    }

    if (domain === "light") {
      return objectId;
    }

    return objectId.replace(/^ledfx_[^_]+_/, "");
  }

  _buildModel() {
    const states = Object.values(this._hass?.states || {}).filter((stateObj) =>
      this._isLedFxEntity(stateObj)
    );
    const devices = new Map();
    const scenes = [];

    for (const stateObj of states) {
      const [domain] = stateObj.entity_id.split(".");
      const entityType = stateObj.attributes.ledfx_entity_type;

      if (entityType === "scene") {
        scenes.push(stateObj);
        continue;
      }

      if (domain === "light" && this._deviceCode(stateObj)) {
        devices.set(this._deviceCode(stateObj), {
          light: stateObj,
          controls: [],
        });
      }
    }

    for (const stateObj of states) {
      const code = this._deviceCode(stateObj);
      if (!code || stateObj.state === "unavailable") {
        continue;
      }
      const [domain] = stateObj.entity_id.split(".");
      if (!["number", "select", "switch"].includes(domain)) {
        continue;
      }
      if (!devices.has(code)) {
        devices.set(code, { light: undefined, controls: [] });
      }
      devices.get(code).controls.push(stateObj);
    }

    return {
      devices: [...devices.values()].sort((a, b) =>
        this._name(a.light).localeCompare(this._name(b.light))
      ),
      scenes: scenes.sort((a, b) => this._name(a).localeCompare(this._name(b))),
    };
  }

  _name(stateObj) {
    return stateObj?.attributes?.friendly_name || stateObj?.entity_id || "";
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  _render() {
    if (!this.shadowRoot || !this._hass) {
      return;
    }

    const model = this._buildModel();
    const body = model.devices.length
      ? model.devices.map((device) => this._renderDevice(device)).join("")
      : `<div class="empty">No LedFX devices found.</div>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          box-sizing: border-box;
          padding: 24px;
        }
        .shell {
          max-width: 1180px;
          margin: 0 auto;
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 20px;
        }
        h1 {
          margin: 0;
          font-size: 28px;
          font-weight: 500;
          letter-spacing: 0;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 16px;
        }
        .device,
        .scenes,
        .empty {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .device {
          min-width: 0;
          overflow: hidden;
        }
        .device-head {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: center;
          padding: 16px;
          border-bottom: 1px solid var(--divider-color);
        }
        h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 500;
          letter-spacing: 0;
          overflow-wrap: anywhere;
        }
        .meta {
          color: var(--secondary-text-color);
          font-size: 13px;
          margin-top: 4px;
          overflow-wrap: anywhere;
        }
        .rows {
          display: grid;
          gap: 12px;
          padding: 16px;
        }
        .row {
          display: grid;
          grid-template-columns: minmax(96px, 1fr) minmax(150px, 2fr);
          gap: 12px;
          align-items: center;
          min-height: 40px;
        }
        label {
          color: var(--secondary-text-color);
          font-size: 13px;
          overflow-wrap: anywhere;
        }
        select,
        input[type="number"],
        input[type="range"] {
          width: 100%;
          box-sizing: border-box;
        }
        input[type="number"],
        select {
          min-height: 40px;
          padding: 0 10px;
          border: 1px solid var(--divider-color);
          border-radius: 6px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
        }
        button {
          min-height: 36px;
          border: 0;
          border-radius: 6px;
          padding: 0 14px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          cursor: pointer;
          font: inherit;
        }
        button.secondary {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        .toggle {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          justify-self: end;
        }
        .scene-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          padding: 16px;
        }
        .scenes {
          margin-bottom: 16px;
        }
        .scenes h2 {
          padding: 16px 16px 0;
        }
        .empty {
          padding: 24px;
          color: var(--secondary-text-color);
        }
        @media (max-width: 640px) {
          :host {
            padding: 12px;
          }
          header {
            align-items: flex-start;
            flex-direction: column;
          }
          .grid {
            grid-template-columns: 1fr;
          }
          .row {
            grid-template-columns: 1fr;
          }
          .toggle {
            justify-self: start;
          }
        }
      </style>
      <div class="shell">
        <header>
          <h1>LedFX</h1>
          <button class="secondary" data-action="refresh">Refresh</button>
        </header>
        ${this._renderScenes(model.scenes)}
        <section class="grid">${body}</section>
      </div>
    `;
  }

  _renderScenes(scenes) {
    const activeScenes = scenes.filter((scene) => scene.state !== "unavailable");
    if (!activeScenes.length) {
      return "";
    }

    return `
      <section class="scenes">
        <h2>Scenes</h2>
        <div class="scene-list">
          ${activeScenes.map((scene) => this._renderScene(scene)).join("")}
        </div>
      </section>
    `;
  }

  _renderScene(scene) {
    const [domain] = scene.entity_id.split(".");
    const action = domain === "button" ? "press" : scene.state === "on" ? "turn_off" : "turn_on";

    return `
      <button
        class="${scene.state === "on" ? "" : "secondary"}"
        data-entity="${this._escape(scene.entity_id)}"
        data-action="${action}"
      >
        ${this._escape(this._name(scene))}
      </button>
    `;
  }

  _renderDevice(device) {
    const light = device.light;
    const controls = device.controls.sort((a, b) => this._name(a).localeCompare(this._name(b)));
    const effect = light?.attributes?.effect;
    const effects = light?.attributes?.effect_list || [];

    return `
      <article class="device">
        <div class="device-head">
          <div>
            <h2>${this._escape(this._name(light))}</h2>
            ${effect ? `<div class="meta">${this._escape(effect)}</div>` : ""}
          </div>
          ${
            light
              ? `<label class="toggle">
                  <input
                    type="checkbox"
                    data-action="light-toggle"
                    data-entity="${this._escape(light.entity_id)}"
                    ${light.state === "on" ? "checked" : ""}
                  >
                  Power
                </label>`
              : ""
          }
        </div>
        <div class="rows">
          ${
            light
              ? this._renderLightControls(light, effects)
              : ""
          }
          ${controls.map((control) => this._renderControl(control)).join("")}
        </div>
      </article>
    `;
  }

  _renderLightControls(light, effects) {
    const brightness = Number(light.attributes.brightness || 0);

    return `
      <div class="row">
        <label>Brightness</label>
        <input
          type="range"
          min="0"
          max="255"
          step="1"
          value="${brightness}"
          data-action="brightness"
          data-entity="${this._escape(light.entity_id)}"
        >
      </div>
      ${
        effects.length
          ? `<div class="row">
              <label>Effect</label>
              <select data-action="effect" data-entity="${this._escape(light.entity_id)}">
                ${effects.map((effect) => `
                  <option
                    value="${this._escape(effect)}"
                    ${effect === light.attributes.effect ? "selected" : ""}
                  >
                    ${this._escape(effect)}
                  </option>
                `).join("")}
              </select>
            </div>`
          : ""
      }
    `;
  }

  _renderControl(control) {
    const [domain] = control.entity_id.split(".");
    if (domain === "number") {
      return this._renderNumber(control);
    }
    if (domain === "select") {
      return this._renderSelect(control);
    }
    if (domain === "switch") {
      return this._renderSwitch(control);
    }
    return "";
  }

  _renderNumber(control) {
    const min = Number(control.attributes.min ?? control.attributes.native_min_value ?? 0);
    const max = Number(control.attributes.max ?? control.attributes.native_max_value ?? 100);
    const step = Number(control.attributes.step ?? 0.1);
    const value = Number(control.state);

    return `
      <div class="row">
        <label>${this._escape(this._name(control))}</label>
        <input
          type="range"
          min="${min}"
          max="${max}"
          step="${step}"
          value="${Number.isFinite(value) ? value : min}"
          data-action="number"
          data-entity="${this._escape(control.entity_id)}"
        >
      </div>
    `;
  }

  _renderSelect(control) {
    const options = control.attributes.options || [];

    return `
      <div class="row">
        <label>${this._escape(this._name(control))}</label>
        <select data-action="select" data-entity="${this._escape(control.entity_id)}">
          ${options.map((option) => `
            <option
              value="${this._escape(option)}"
              ${option === control.state ? "selected" : ""}
            >
              ${this._escape(option)}
            </option>
          `).join("")}
        </select>
      </div>
    `;
  }

  _renderSwitch(control) {
    return `
      <div class="row">
        <label>${this._escape(this._name(control))}</label>
        <label class="toggle">
          <input
            type="checkbox"
            data-action="switch"
            data-entity="${this._escape(control.entity_id)}"
            ${control.state === "on" ? "checked" : ""}
          >
          Enabled
        </label>
      </div>
    `;
  }

  _handleClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target || !this._hass) {
      return;
    }

    const action = target.dataset.action;
    const entityId = target.dataset.entity;
    if (action === "refresh") {
      this._hass.callService("homeassistant", "update_entity", {
        entity_id: Object.keys(this._hass.states).filter((entityId) =>
          this._isLedFxEntity(this._hass.states[entityId])
        ),
      });
      return;
    }
    if (action === "press") {
      this._hass.callService("button", "press", { entity_id: entityId });
    }
    if (action === "turn_on" || action === "turn_off") {
      this._hass.callService("switch", action, { entity_id: entityId });
    }
  }

  _handleChange(event) {
    const target = event.target.closest("[data-action]");
    if (!target || !this._hass) {
      return;
    }

    const action = target.dataset.action;
    const entityId = target.dataset.entity;

    if (action === "light-toggle") {
      this._hass.callService("light", target.checked ? "turn_on" : "turn_off", {
        entity_id: entityId,
      });
    }
    if (action === "effect") {
      this._hass.callService("light", "turn_on", {
        entity_id: entityId,
        effect: target.value,
      });
    }
    if (action === "select") {
      this._hass.callService("select", "select_option", {
        entity_id: entityId,
        option: target.value,
      });
    }
    if (action === "switch") {
      this._hass.callService("switch", target.checked ? "turn_on" : "turn_off", {
        entity_id: entityId,
      });
    }
    if (action === "brightness") {
      this._hass.callService("light", "turn_on", {
        entity_id: entityId,
        brightness: Number(target.value),
      });
    }
    if (action === "number") {
      this._hass.callService("number", "set_value", {
        entity_id: entityId,
        value: Number(target.value),
      });
    }
  }
}

customElements.define("ledfx-panel", LedFxPanel);
