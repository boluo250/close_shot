const { request } = require("../../../utils/request");
const { ensureLogin } = require("../../../utils/auth");

const SHOOTING_TYPES = ["人像", "情侣", "亲子", "商拍", "活动", "婚礼", "旅拍", "宠物", "美食", "建筑"];
const PRICE_RANGES = ["199-399", "399-699", "699+"];

Page({
  data: {
    step: 1,        // 当前步骤 1-3
    totalSteps: 3,
    submitting: false,

    // Step 1: 实名认证
    realName: "",
    idCardNumber: "",

    // Step 2: 摄影师身份
    shootingTypes: SHOOTING_TYPES,
    selectedTypes: [],     // 选中的拍摄类型
    selectedTypeMap: {},   // 用于模板判断选中态
    typeDisabledMap: {},   // 已达到上限时，未选项置灰
    portfolioLink: "",

    // Step 3: 联系方式
    phone: "",
    wechatId: "",

    // 可选
    city: "",
    priceRanges: PRICE_RANGES,
    priceRangeIndex: -1,
    priceRange: "",

    // 表单校验
    step1Valid: false,
    step2Valid: false,
    step3Valid: false,
  },

  onLoad() {
    // 尝试获取手机号自动填充
    this._syncSelectedTypeState([]);
    this._loadCertificationStatus();
  },

  async _loadCertificationStatus() {
    try {
      await ensureLogin();
      const res = await request("/me/photographer/certification", { method: "GET", auth: true });
      // 如果已在审核中，跳转审核页
      if (res.status === "pending") {
        wx.redirectTo({ url: "/pages/auth/review/index" });
        return;
      }
      // 如果已通过认证，跳转工作台
      if (res.status === "approved") {
        wx.showToast({ title: "你已通过认证", icon: "none" });
        wx.switchTab({ url: "/pages/mine/index" });
        return;
      }
    } catch (e) {
      // 未申请过，正常显示认证表单
    }
  },

  // ========== Step 1: 实名认证 ==========
  onRealNameInput(e) {
    this.setData({ realName: e.detail.value });
    this._validateStep1();
  },

  onIdCardInput(e) {
    this.setData({ idCardNumber: e.detail.value });
    this._validateStep1();
  },

  _validateStep1() {
    const { realName, idCardNumber } = this.data;
    const valid = realName.length >= 2 && this._isValidIdCard(idCardNumber);
    this.setData({ step1Valid: valid });
  },

  _isValidIdCard(num) {
    return /^\d{15}$|^\d{17}[\dXx]$/.test(num);
  },

  // ========== Step 2: 摄影师身份 ==========
  toggleShootingType(e) {
    const type = e.currentTarget.dataset.type;
    if (!type) return;
    let selected = [...this.data.selectedTypes];
    const idx = selected.indexOf(type);
    if (idx > -1) {
      selected.splice(idx, 1);
    } else {
      if (selected.length >= 3) {
        wx.showToast({ title: "拍摄类型最多选择 3 个", icon: "none" });
        return;
      }
      selected.push(type);
    }
    this._syncSelectedTypeState(selected);
    this._validateStep2();
  },

  _syncSelectedTypeState(selectedTypes) {
    const selectedTypeMap = {};
    selectedTypes.forEach((type) => {
      selectedTypeMap[type] = true;
    });

    const typeDisabledMap = {};
    const isMaxSelected = selectedTypes.length >= 3;
    this.data.shootingTypes.forEach((type) => {
      typeDisabledMap[type] = isMaxSelected && !selectedTypeMap[type];
    });

    this.setData({
      selectedTypes,
      selectedTypeMap,
      typeDisabledMap,
    });
  },

  onPortfolioLinkInput(e) {
    this.setData({ portfolioLink: e.detail.value });
  },

  _validateStep2() {
    const { selectedTypes } = this.data;
    const valid = selectedTypes.length > 0;
    this.setData({ step2Valid: valid });
  },

  // ========== Step 3: 联系方式 ==========
  onPhoneInput(e) {
    this.setData({ phone: e.detail.value });
    this._validateStep3();
  },

  onWechatInput(e) {
    this.setData({ wechatId: e.detail.value });
    this._validateStep3();
  },

  onCityInput(e) {
    this.setData({ city: e.detail.value });
  },

  onPriceRangeChange(e) {
    const idx = Number(e.detail.value);
    this.setData({
      priceRangeIndex: idx,
      priceRange: PRICE_RANGES[idx],
    });
  },

  _validateStep3() {
    const { phone, wechatId } = this.data;
    const valid = /^1\d{10}$/.test(phone) && wechatId.length > 0;
    this.setData({ step3Valid: valid });
  },

  // ========== 步骤导航 ==========
  nextStep() {
    const { step } = this.data;
    if (step === 1 && !this.data.step1Valid) {
      wx.showToast({ title: "请完善实名认证信息", icon: "none" });
      return;
    }
    if (step === 2 && !this.data.step2Valid) {
      wx.showToast({ title: "请至少选择1个拍摄类型", icon: "none" });
      return;
    }
    if (step < 3) {
      this.setData({ step: step + 1 });
    }
  },

  prevStep() {
    const { step } = this.data;
    if (step > 1) {
      this.setData({ step: step - 1 });
    }
  },

  // ========== 提交认证 ==========
  async submitApply() {
    if (this.data.submitting) return;

    if (!this.data.step3Valid) {
      wx.showToast({ title: "请填写联系方式", icon: "none" });
      return;
    }

    this.setData({ submitting: true });
    try {
      await ensureLogin();
      const data = {
        real_name: this.data.realName,
        id_card_number: this.data.idCardNumber,
        shooting_types: this.data.selectedTypes,
        portfolio_link: this.data.portfolioLink || null,
        phone: this.data.phone,
        wechat_id: this.data.wechatId,
        city: this.data.city || null,
        price_range: this.data.priceRange || null,
      };
      await request("/me/photographer/apply", { method: "POST", data, auth: true });
      wx.showToast({ title: "已提交，等待审核", icon: "none" });
      wx.redirectTo({ url: "/pages/auth/review/index" });
    } catch (e) {
      wx.showToast({ title: e.message || "提交失败，请稍后重试", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  },

  onBackMine() {
    wx.switchTab({ url: "/pages/mine/index" });
  },
});
