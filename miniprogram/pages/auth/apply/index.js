const { request } = require("../../../utils/request");
const { ensureLogin } = require("../../../utils/auth");

const SHOOTING_TYPES = ["人像", "情侣", "亲子", "商拍", "活动", "婚礼", "旅拍", "宠物", "美食", "建筑"];
const EXPERIENCE_OPTIONS = ["1年内", "1-3年", "3年以上"];
const PRICE_RANGES = ["199-399", "399-699", "699+"];

Page({
  data: {
    step: 1,        // 当前步骤 1-3
    totalSteps: 3,
    submitting: false,

    // Step 1: 实名认证
    realName: "",
    idCardNumber: "",
    idCardFrontUrl: "",
    idCardBackUrl: "",

    // Step 2: 摄影师身份
    shootingTypes: SHOOTING_TYPES,
    selectedTypes: [],     // 选中的拍摄类型
    experienceOptions: EXPERIENCE_OPTIONS,
    experienceIndex: -1,   // picker 选中索引
    experienceYears: "",
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

  chooseIdCardFront() {
    this._chooseAndUploadImage("id_card", (url) => {
      this.setData({ idCardFrontUrl: url });
      this._validateStep1();
    });
  },

  chooseIdCardBack() {
    this._chooseAndUploadImage("id_card", (url) => {
      this.setData({ idCardBackUrl: url });
      this._validateStep1();
    });
  },

  _validateStep1() {
    const { realName, idCardNumber, idCardFrontUrl, idCardBackUrl } = this.data;
    const valid = realName.length >= 2 && this._isValidIdCard(idCardNumber) && idCardFrontUrl && idCardBackUrl;
    this.setData({ step1Valid: valid });
  },

  _isValidIdCard(num) {
    return /^\d{15}$|^\d{17}[\dXx]$/.test(num);
  },

  // ========== Step 2: 摄影师身份 ==========
  toggleShootingType(e) {
    const type = e.currentTarget.dataset.type;
    let selected = [...this.data.selectedTypes];
    const idx = selected.indexOf(type);
    if (idx > -1) {
      selected.splice(idx, 1);
    } else {
      selected.push(type);
    }
    this.setData({ selectedTypes: selected });
    this._validateStep2();
  },

  onExperienceChange(e) {
    const idx = Number(e.detail.value);
    this.setData({
      experienceIndex: idx,
      experienceYears: EXPERIENCE_OPTIONS[idx],
    });
    this._validateStep2();
  },

  onPortfolioLinkInput(e) {
    this.setData({ portfolioLink: e.detail.value });
  },

  _validateStep2() {
    const { selectedTypes, experienceYears } = this.data;
    const valid = selectedTypes.length > 0 && experienceYears.length > 0;
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
      wx.showToast({ title: "请选择拍摄类型和从业年限", icon: "none" });
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
        id_card_front_url: this.data.idCardFrontUrl,
        id_card_back_url: this.data.idCardBackUrl,
        shooting_types: this.data.selectedTypes,
        experience_years: this.data.experienceYears,
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

  // ========== 图片上传工具 ==========
  _chooseAndUploadImage(prefix, callback) {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: (res) => {
        const tempPath = res.tempFiles[0].tempFilePath;
        const filename = tempPath.split("/").pop();
        wx.showLoading({ title: "上传中..." });
        this._uploadFile(tempPath, filename, prefix, callback);
      },
    });
  },

  async _uploadFile(filePath, filename, prefix, callback) {
    try {
      // 1) 获取预签名 URL
      const presign = await request("/upload/presign", {
        method: "POST",
        data: { filename, prefix, content_type: "image/jpeg" },
        auth: true,
      });

      // 2) 上传到 S3/MinIO
      await new Promise((resolve, reject) => {
        wx.uploadFile({
          url: presign.url,
          filePath,
          name: "file",
          header: presign.headers || {},
          formData: {},
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 400) resolve(res);
            else reject(new Error("上传失败"));
          },
          fail: reject,
        });
      });

      wx.hideLoading();
      // 使用代理 URL
      const imageUrl = presign.proxy_url || presign.public_url || `/media/${presign.object_key}`;
      callback(imageUrl);
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: "图片上传失败", icon: "none" });
    }
  },

  // 预览图片
  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    if (url) {
      wx.previewImage({ urls: [url], current: url });
    }
  },

  onBackMine() {
    wx.switchTab({ url: "/pages/mine/index" });
  },
});
