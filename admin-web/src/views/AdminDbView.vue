<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>数据库浏览（只读）</span>
        <el-button :loading="loading" @click="reloadCurrent">刷新</el-button>
      </div>
    </template>

    <el-alert
      style="margin-bottom: 12px"
      type="info"
      :closable="false"
      title="仅管理员可访问；仅支持白名单业务表；仅提供分页只读预览。"
    />

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="10">
        <el-select
          v-model="tableName"
          filterable
          placeholder="请选择要浏览的数据表"
          style="width: 100%"
          @change="onTableChange"
        >
          <el-option v-for="name in tables" :key="name" :label="name" :value="name" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-input-number v-model="pageSize" :min="10" :max="200" :step="10" @change="onPageSizeChange" />
      </el-col>
    </el-row>

    <el-table :data="rows" v-loading="loadingRows" stripe>
      <el-table-column
        v-for="col in columns"
        :key="col"
        :prop="col"
        :label="col"
        min-width="160"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ formatValue(row[col]) }}
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadRows"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../lib/api";

type TableListResp = {
  tables: string[];
};

type RowsResp = {
  table: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
};

const loading = ref(false);
const loadingRows = ref(false);
const tables = ref<string[]>([]);
const tableName = ref("");
const columns = ref<string[]>([]);
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

async function loadTables() {
  const { data } = await api.get<TableListResp>("/admin/db/tables");
  tables.value = data.tables || [];
  if (!tableName.value && tables.value.length) {
    tableName.value = tables.value[0];
  }
}

async function loadRows() {
  if (!tableName.value) return;
  loadingRows.value = true;
  try {
    const { data } = await api.get<RowsResp>("/admin/db/table-preview", {
      params: {
        table: tableName.value,
        limit: pageSize.value,
        offset: (page.value - 1) * pageSize.value
      }
    });
    columns.value = data.columns || [];
    rows.value = data.rows || [];
    total.value = data.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载数据失败");
  } finally {
    loadingRows.value = false;
  }
}

async function reloadCurrent() {
  loading.value = true;
  try {
    await loadTables();
    await loadRows();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "刷新失败");
  } finally {
    loading.value = false;
  }
}

function onTableChange() {
  page.value = 1;
  void loadRows();
}

function onPageSizeChange() {
  page.value = 1;
  void loadRows();
}

function formatValue(v: unknown) {
  if (v === null || v === undefined) return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

onMounted(async () => {
  await reloadCurrent();
});
</script>
