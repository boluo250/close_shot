<template>
  <div>
    <el-form inline style="margin-bottom: 12px">
      <el-form-item label="名称">
        <el-input v-model="createForm.name" style="width: 200px" />
      </el-form-item>
      <el-form-item label="价格(元)">
        <el-input v-model.number="createForm.priceYuan" style="width: 120px" />
      </el-form-item>
      <el-form-item label="时长(分钟)">
        <el-input v-model.number="createForm.duration_minutes" style="width: 120px" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="createForm.is_active" />
      </el-form-item>
    </el-form>

    <el-form style="margin-bottom: 12px">
      <el-form-item label="描述" label-width="60px">
        <el-input v-model="createForm.description" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="creating" @click="create">新增套餐</el-button>
        <el-button :loading="loading" style="margin-left: 8px" @click="load">刷新</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column label="名称">
        <template #default="{ row }">
          <el-input v-model="row.name" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="价格(元)" width="130">
        <template #default="{ row }">
          <el-input v-model.number="row._priceYuan" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="时长" width="110">
        <template #default="{ row }">
          <el-input v-model.number="row.duration_minutes" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" />
        </template>
      </el-table-column>
      <el-table-column label="描述">
        <template #default="{ row }">
          <el-input v-model="row.description" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" :loading="row._saving" @click="saveRow(row)">保存</el-button>
          <el-button size="small" type="danger" :loading="row._deleting" @click="delRow(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";

type PackageItem = {
  id: number;
  name: string;
  price_cents: number;
  duration_minutes?: number | null;
  description?: string | null;
  is_active: boolean;
  _priceYuan?: number;
  _saving?: boolean;
  _deleting?: boolean;
};

const loading = ref(false);
const creating = ref(false);
const items = ref<PackageItem[]>([]);

const createForm = reactive({
  name: "",
  priceYuan: 199,
  duration_minutes: 30,
  description: "",
  is_active: true
});

function toYuan(cents: number) {
  return Math.round(cents / 100);
}
function toCents(yuan: number) {
  return Math.round((yuan || 0) * 100);
}

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get<{ items: PackageItem[] }>("/studio/packages");
    items.value = (data.items || []).map((x) => ({ ...x, _priceYuan: toYuan(x.price_cents) }));
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载失败（请用摄影师账号登录）");
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!createForm.name) {
    ElMessage.warning("请填写名称");
    return;
  }
  creating.value = true;
  try {
    const payload = {
      name: createForm.name,
      price_cents: toCents(createForm.priceYuan),
      duration_minutes: createForm.duration_minutes,
      description: createForm.description,
      is_active: createForm.is_active
    };
    const { data } = await api.post<PackageItem>("/studio/packages", payload);
    items.value.unshift({ ...data, _priceYuan: toYuan(data.price_cents) });
    createForm.name = "";
    createForm.description = "";
    ElMessage.success("已新增");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "新增失败");
  } finally {
    creating.value = false;
  }
}

async function saveRow(row: PackageItem) {
  row._saving = true;
  try {
    await api.put(`/studio/packages/${row.id}`, {
      name: row.name,
      price_cents: toCents(row._priceYuan || 0),
      duration_minutes: row.duration_minutes,
      description: row.description,
      is_active: row.is_active
    });
    ElMessage.success("已保存");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    row._saving = false;
  }
}

async function delRow(row: PackageItem) {
  row._deleting = true;
  try {
    await api.delete(`/studio/packages/${row.id}`);
    items.value = items.value.filter((x) => x.id !== row.id);
    ElMessage.success("已删除");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  } finally {
    row._deleting = false;
  }
}

onMounted(load);
</script>

