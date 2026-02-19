<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>摄影师认证审核</span>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>

    <!-- 筛选栏 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-select v-model="filters.status" placeholder="认证状态" clearable @change="load">
          <el-option label="全部" value="" />
          <el-option label="⏳ 待审核" value="pending" />
          <el-option label="✅ 已通过" value="approved" />
          <el-option label="❌ 已驳回" value="rejected" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索姓名/手机号"
          clearable
          @keyup.enter="load"
          @clear="load"
        />
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="load">搜索</el-button>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-table :data="items" v-loading="loading" style="width: 100%" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="头像" width="70">
        <template #default="{ row }">
          <el-avatar :src="row.avatar_url" :size="36" />
        </template>
      </el-table-column>
      <el-table-column label="昵称" width="140">
        <template #default="{ row }">
          {{ row.display_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="真实姓名" width="100">
        <template #default="{ row }">
          {{ row.real_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="手机号" width="130">
        <template #default="{ row }">
          {{ row.phone || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="从业年限" width="100">
        <template #default="{ row }">
          {{ row.experience_years || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="城市" width="80">
        <template #default="{ row }">
          {{ row.city || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="认证等级" width="90">
        <template #default="{ row }">
          <span v-if="row.certification_level > 0">Lv{{ row.certification_level }}</span>
          <span v-else style="color: #999">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'pending'"
            size="small"
            type="success"
            @click="handleApprove(row)"
          >通过</el-button>
          <el-button
            v-if="row.status === 'pending'"
            size="small"
            type="danger"
            @click="openReject(row)"
          >驳回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>

  <!-- 详情弹窗 -->
  <el-dialog v-model="detailVisible" title="认证详情" width="640px">
    <template v-if="currentItem">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ currentItem.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(currentItem.status)" size="small">
            {{ statusLabel(currentItem.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="昵称">{{ currentItem.display_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="认证等级">
          {{ currentItem.certification_level > 0 ? `Lv${currentItem.certification_level}` : '未认证' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">实名信息</el-divider>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="真实姓名">{{ currentItem.real_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="身份证号">{{ maskIdCard(currentItem.id_card_number) }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="currentItem.id_card_front_url || currentItem.id_card_back_url" style="display: flex; gap: 12px; margin-top: 12px">
        <div v-if="currentItem.id_card_front_url" style="flex: 1">
          <div style="font-size: 12px; color: #999; margin-bottom: 4px">人像面</div>
          <el-image
            :src="currentItem.id_card_front_url"
            :preview-src-list="[currentItem.id_card_front_url]"
            style="width: 100%; height: 140px; border-radius: 8px"
            fit="cover"
          />
        </div>
        <div v-if="currentItem.id_card_back_url" style="flex: 1">
          <div style="font-size: 12px; color: #999; margin-bottom: 4px">国徽面</div>
          <el-image
            :src="currentItem.id_card_back_url"
            :preview-src-list="[currentItem.id_card_back_url]"
            style="width: 100%; height: 140px; border-radius: 8px"
            fit="cover"
          />
        </div>
      </div>

      <el-divider content-position="left">联系方式</el-divider>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="手机号">{{ currentItem.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="微信号">{{ currentItem.wechat_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="城市">{{ currentItem.city || '-' }}</el-descriptions-item>
        <el-descriptions-item label="报价区间">
          {{ currentItem.price_range ? `¥${currentItem.price_range}` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="个人主页" :span="2">
          <a v-if="currentItem.portfolio_link" :href="currentItem.portfolio_link" target="_blank" style="color: #409eff">
            {{ currentItem.portfolio_link }}
          </a>
          <span v-else style="color: #999">-</span>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="currentItem.reject_reason" style="margin-top: 16px">
        <el-alert :title="`驳回原因：${currentItem.reject_reason}`" type="error" :closable="false" />
      </div>

      <div style="margin-top: 16px; text-align: right">
        <el-button
          v-if="currentItem.status === 'pending'"
          type="success"
          @click="handleApprove(currentItem); detailVisible = false"
        >审核通过</el-button>
        <el-button
          v-if="currentItem.status === 'pending'"
          type="danger"
          @click="detailVisible = false; openReject(currentItem)"
        >驳回</el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>

  <!-- 驳回弹窗 -->
  <el-dialog v-model="rejectVisible" title="驳回认证" width="440px">
    <el-form>
      <el-form-item label="驳回原因" required>
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="3"
          placeholder="请输入驳回原因（用户可见）"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="rejectVisible = false">取消</el-button>
      <el-button type="danger" :loading="reviewing" @click="handleReject">确认驳回</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api } from "../lib/api";

// ---------- 类型 ----------
type CertificationItem = {
  id: number;
  user_id: number;
  display_name: string | null;
  avatar_url: string | null;
  status: string;
  reject_reason: string | null;
  certification_level: number;
  real_name: string | null;
  id_card_number: string | null;
  id_card_front_url: string | null;
  id_card_back_url: string | null;
  experience_years: string | null;
  portfolio_link: string | null;
  phone: string | null;
  wechat_id: string | null;
  city: string | null;
  price_range: string | null;
  created_at: string;
  updated_at: string;
};

// ---------- 状态 ----------
const loading = ref(false);
const reviewing = ref(false);
const items = ref<CertificationItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;

const filters = reactive({
  status: "pending" as string,
  keyword: ""
});

// 详情弹窗
const detailVisible = ref(false);
const currentItem = ref<CertificationItem | null>(null);

// 驳回弹窗
const rejectVisible = ref(false);
const rejectReason = ref("");
const rejectTarget = ref<CertificationItem | null>(null);

// ---------- 数据加载 ----------
async function load() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      limit: pageSize,
      offset: (page.value - 1) * pageSize
    };
    if (filters.status) params.status = filters.status;
    if (filters.keyword) params.keyword = filters.keyword;

    const { data } = await api.get<{ items: CertificationItem[]; total: number }>(
      "/admin/certifications",
      { params }
    );
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败（需要管理员权限）");
  } finally {
    loading.value = false;
  }
}

// ---------- 详情 ----------
function openDetail(row: CertificationItem) {
  currentItem.value = row;
  detailVisible.value = true;
}

// ---------- 审核通过 ----------
async function handleApprove(row: CertificationItem) {
  try {
    await ElMessageBox.confirm(
      `确定通过「${row.display_name || row.real_name || `#${row.id}`}」的认证吗？`,
      "审核通过",
      { confirmButtonText: "通过", cancelButtonText: "取消", type: "success" }
    );
  } catch {
    return; // 取消
  }

  reviewing.value = true;
  try {
    const { data } = await api.post<CertificationItem>(
      `/admin/certifications/${row.id}/review`,
      { action: "approve" }
    );
    // 更新列表中的行
    const idx = items.value.findIndex((x) => x.id === row.id);
    if (idx >= 0) items.value[idx] = data;
    if (currentItem.value?.id === row.id) currentItem.value = data;
    ElMessage.success("已通过认证");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  } finally {
    reviewing.value = false;
  }
}

// ---------- 驳回 ----------
function openReject(row: CertificationItem) {
  rejectTarget.value = row;
  rejectReason.value = "";
  rejectVisible.value = true;
}

async function handleReject() {
  if (!rejectReason.value.trim()) {
    ElMessage.warning("请填写驳回原因");
    return;
  }
  if (!rejectTarget.value) return;

  reviewing.value = true;
  try {
    const { data } = await api.post<CertificationItem>(
      `/admin/certifications/${rejectTarget.value.id}/review`,
      { action: "reject", reject_reason: rejectReason.value.trim() }
    );
    const idx = items.value.findIndex((x) => x.id === rejectTarget.value!.id);
    if (idx >= 0) items.value[idx] = data;
    rejectVisible.value = false;
    ElMessage.success("已驳回");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  } finally {
    reviewing.value = false;
  }
}

// ---------- 工具函数 ----------
function statusLabel(s: string) {
  return { pending: "待审核", approved: "已通过", rejected: "已驳回" }[s] || s;
}

function statusType(s: string) {
  return { pending: "warning", approved: "success", rejected: "danger" }[s] as any || "info";
}

function maskIdCard(num: string | null) {
  if (!num) return "-";
  if (num.length <= 6) return num;
  return num.slice(0, 3) + "***" + num.slice(-4);
}

onMounted(load);
</script>
