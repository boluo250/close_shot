const CONSENT_STORAGE_KEY = "cs_legal_consent_v1";

function hasAcceptedConsent() {
  return !!wx.getStorageSync(CONSENT_STORAGE_KEY);
}

function markConsentAccepted() {
  wx.setStorageSync(CONSENT_STORAGE_KEY, {
    agreed: true,
    acceptedAt: Date.now()
  });
}

module.exports = {
  CONSENT_STORAGE_KEY,
  hasAcceptedConsent,
  markConsentAccepted
};
