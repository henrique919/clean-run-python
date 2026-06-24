import createContextHook from "@nkzw/create-context-hook";
import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { buildDemoItems, buildDemoSettings } from "@/lib/demoSeed";
import { addDays, makeId, nextCode } from "@/lib/format";
import {
  AuditEvent,
  CloseoutEvidence,
  Comment,
  InspectionEvent,
  IssueEvent,
  Item,
  ItemStatus,
  ProjectConfig,
  RectificationEvidence,
  Settings,
  SubProfile,
} from "@/types/models";

const ITEMS_KEY = "cleanrun-iq:items:v1";
const SETTINGS_KEY = "cleanrun-iq:settings:v1";

type CreateInput = Omit<
  Item,
  | "id"
  | "code"
  | "createdAt"
  | "updatedAt"
  | "rectificationEvidence"
  | "closeoutEvidence"
  | "comments"
  | "issueHistory"
  | "inspectionHistory"
  | "auditEvents"
  | "sync"
> & { status?: ItemStatus };

function audit(it: Item, ev: AuditEvent): Item {
  return { ...it, auditEvents: [...it.auditEvents, ev], updatedAt: ev.at };
}

export const [AppStoreProvider, useAppStore] = createContextHook(() => {
  const [items, setItems] = useState<Item[]>([]);
  const [settings, setSettings] = useState<Settings>(() => buildDemoSettings());
  const [hydrated, setHydrated] = useState<boolean>(false);
  const [online, setOnline] = useState<boolean>(true);

  // Initial hydration from AsyncStorage (or seed on first run).
  const hydration = useQuery({
    queryKey: ["cleanrun-hydrate"],
    queryFn: async () => {
      const [rawItems, rawSettings] = await Promise.all([
        AsyncStorage.getItem(ITEMS_KEY),
        AsyncStorage.getItem(SETTINGS_KEY),
      ]);
      let nextItems: Item[];
      let nextSettings: Settings;
      try {
        nextItems = rawItems ? (JSON.parse(rawItems) as Item[]) : buildDemoItems();
      } catch {
        nextItems = buildDemoItems();
      }
      try {
        nextSettings = rawSettings ? (JSON.parse(rawSettings) as Settings) : buildDemoSettings();
      } catch {
        nextSettings = buildDemoSettings();
      }
      if (!rawItems) await AsyncStorage.setItem(ITEMS_KEY, JSON.stringify(nextItems));
      if (!rawSettings) await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(nextSettings));
      return { items: nextItems, settings: nextSettings };
    },
    staleTime: Infinity,
  });

  useEffect(() => {
    if (hydration.data && !hydrated) {
      setItems(hydration.data.items);
      setSettings(hydration.data.settings);
      setHydrated(true);
    }
  }, [hydration.data, hydrated]);

  useEffect(() => {
    const unsub = NetInfo.addEventListener((state) => {
      setOnline(Boolean(state.isConnected));
    });
    return () => unsub();
  }, []);

  const persistItems = useCallback((next: Item[]) => {
    setItems(next);
    AsyncStorage.setItem(ITEMS_KEY, JSON.stringify(next)).catch((e) =>
      console.warn("[CleanRun] failed to persist items", e),
    );
  }, []);

  const persistSettings = useCallback((next: Settings) => {
    setSettings(next);
    AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(next)).catch((e) =>
      console.warn("[CleanRun] failed to persist settings", e),
    );
  }, []);

  const patch = useCallback(
    (id: string, mutator: (it: Item) => Item) => {
      setItems((prev) => {
        const next = prev.map((it) =>
          it.id === id ? { ...mutator({ ...it }), sync: online ? ("synced" as const) : ("pending" as const) } : it,
        );
        AsyncStorage.setItem(ITEMS_KEY, JSON.stringify(next)).catch(() => {});
        return next;
      });
    },
    [online],
  );

  const create = useCallback(
    (input: CreateInput): Item => {
      const now = new Date().toISOString();
      const code = nextCode(items, input.type);
      const item: Item = {
        ...input,
        id: makeId(),
        code,
        status: input.status ?? "open",
        createdAt: now,
        updatedAt: now,
        rectificationEvidence: [],
        closeoutEvidence: [],
        comments: [],
        issueHistory: [],
        inspectionHistory: [],
        auditEvents: [
          {
            at: now,
            action: input.voiceTranscript ? `Created (${code}) via Voice-to-Note` : `Created (${code})`,
            by: input.createdBy,
          },
        ],
        sync: online ? "synced" : "pending",
      };
      persistItems([item, ...items]);
      return item;
    },
    [items, online, persistItems],
  );

  const issue = useCallback(
    (id: string, opts: { to: string; by?: string; note?: string; reissue?: boolean }) => {
      const at = new Date().toISOString();
      const ev: IssueEvent = { at, to: opts.to, by: opts.by, note: opts.note, reissue: opts.reissue };
      patch(id, (it) =>
        audit(
          {
            ...it,
            subcontractor: opts.to || it.subcontractor,
            status: "issued",
            issuedAt: it.issuedAt ?? at,
            issueHistory: [...it.issueHistory, ev],
            rejectionReason: opts.reissue ? undefined : it.rejectionReason,
          },
          { at, action: opts.reissue ? `Re-issued to ${opts.to}` : `Issued to ${opts.to}`, by: opts.by, note: opts.note },
        ),
      );
    },
    [patch],
  );

  const markInProgress = useCallback(
    (id: string, by?: string) => {
      const at = new Date().toISOString();
      patch(id, (it) => audit({ ...it, status: "in_progress", inProgressAt: it.inProgressAt ?? at }, { at, action: "Marked in progress", by }));
    },
    [patch],
  );

  const markReady = useCallback(
    (id: string, by?: string, note?: string) => {
      const at = new Date().toISOString();
      patch(id, (it) => audit({ ...it, status: "ready_for_review", readyForReviewAt: at }, { at, action: "Marked ready for review", by, note }));
    },
    [patch],
  );

  const startInspection = useCallback(
    (id: string, by: string) => {
      const at = new Date().toISOString();
      const ev: InspectionEvent = { at, by, action: "started" };
      patch(id, (it) => audit({ ...it, status: "under_inspection", underInspectionAt: at, inspectionHistory: [...it.inspectionHistory, ev] }, { at, action: "Inspection started", by }));
    },
    [patch],
  );

  const reject = useCallback(
    (id: string, by: string, reason: string) => {
      const at = new Date().toISOString();
      const ev: InspectionEvent = { at, by, action: "rejected", reason };
      patch(id, (it) => audit({ ...it, status: "rejected", rejectionReason: reason, inspectionHistory: [...it.inspectionHistory, ev] }, { at, action: "Rejected on inspection", by, note: reason }));
    },
    [patch],
  );

  const closeWithEvidence = useCallback(
    (id: string, evidence: Omit<CloseoutEvidence, "id" | "at">[]) => {
      const at = new Date().toISOString();
      patch(id, (it) => {
        const entries: CloseoutEvidence[] = evidence.map((e) => ({ ...e, id: makeId(), at }));
        const inspection: InspectionEvent[] = it.status === "under_inspection" ? [...it.inspectionHistory, { at, by: entries[0]?.by ?? "Site Manager", action: "accepted" as const }] : it.inspectionHistory;
        return audit(
          {
            ...it,
            status: it.type === "incomplete" ? "complete" : "closed",
            closedAt: at,
            closeoutEvidence: [...it.closeoutEvidence, ...entries],
            inspectionHistory: inspection,
          },
          { at, action: "Closed with evidence", by: entries[0]?.by },
        );
      });
    },
    [patch],
  );

  const completeIncomplete = useCallback(
    (id: string, by: string, note?: string) => {
      const at = new Date().toISOString();
      patch(id, (it) => audit({ ...it, status: "complete", closedAt: at }, { at, action: "Completed (no photo required)", by, note }));
    },
    [patch],
  );

  const reopen = useCallback(
    (id: string, by: string, reason: string) => {
      const at = new Date().toISOString();
      patch(id, (it) => audit({ ...it, status: "in_progress", closedAt: undefined, inProgressAt: at }, { at, action: "Reopened", by, note: reason }));
    },
    [patch],
  );

  const addRectification = useCallback(
    (id: string, ev: Omit<RectificationEvidence, "id" | "at"> & { advanceToReady?: boolean }) => {
      const at = new Date().toISOString();
      patch(id, (it) => {
        const entry: RectificationEvidence = { id: makeId(), at, photo: ev.photo, comment: ev.comment, by: ev.by };
        let next = audit(
          {
            ...it,
            rectificationEvidence: [...it.rectificationEvidence, entry],
            status: it.status === "issued" ? "in_progress" : it.status,
            inProgressAt: it.inProgressAt ?? (it.status === "issued" ? at : it.inProgressAt),
          },
          { at, action: "Rectification evidence added", by: ev.by, note: ev.comment },
        );
        if (ev.advanceToReady) {
          next = audit({ ...next, status: "ready_for_review", readyForReviewAt: at }, { at, action: "Marked ready for review", by: ev.by });
        }
        return next;
      });
    },
    [patch],
  );

  const addComment = useCallback(
    (id: string, c: Omit<Comment, "id" | "at">) => {
      const at = new Date().toISOString();
      patch(id, (it) => audit({ ...it, comments: [...it.comments, { id: makeId(), at, text: c.text, by: c.by }] }, { at, action: "Comment added", by: c.by, note: c.text }));
    },
    [patch],
  );

  const setActiveProject = useCallback(
    (name: string) => {
      const activeProject = settings.projects.includes(name) ? name : settings.projects[0];
      persistSettings({ ...settings, activeProject });
    },
    [settings, persistSettings],
  );

  const addProject = useCallback(
    (name: string) => {
      const clean = name.trim();
      if (!clean || settings.projects.includes(clean)) return;
      const config: ProjectConfig = {
        name: clean,
        address: "",
        buildings: ["Block A"],
        levels: ["L01"],
        units: [],
        rooms: ["Kitchen", "Living", "Bathroom", "Bedroom 1"],
        defaultDueDays: 7,
      };
      persistSettings({ ...settings, projects: [...settings.projects, clean], projectConfigs: { ...settings.projectConfigs, [clean]: config } });
    },
    [settings, persistSettings],
  );

  const updateProjectConfig = useCallback(
    (name: string, patchConfig: Partial<ProjectConfig>) => {
      const current = settings.projectConfigs[name];
      if (!current) return;
      persistSettings({ ...settings, projectConfigs: { ...settings.projectConfigs, [name]: { ...current, ...patchConfig, name } } });
    },
    [settings, persistSettings],
  );

  const addSubcontractor = useCallback(
    (profile: SubProfile) => {
      const name = profile.name.trim();
      if (!name) return;
      const subcontractors = settings.subcontractors.includes(name) ? settings.subcontractors : [...settings.subcontractors, name].sort((a, b) => a.localeCompare(b));
      persistSettings({ ...settings, subcontractors, subProfiles: { ...settings.subProfiles, [name]: { ...profile, name } } });
    },
    [settings, persistSettings],
  );

  const updateProfile = useCallback(
    (name: string, patchProfile: Partial<SubProfile>) => {
      const existing = settings.subProfiles[name];
      if (!existing) return;
      persistSettings({ ...settings, subProfiles: { ...settings.subProfiles, [name]: { ...existing, ...patchProfile, name } } });
    },
    [settings, persistSettings],
  );

  const updateCompany = useCallback(
    (patchSettings: Partial<Pick<Settings, "company" | "preparedBy">>) => {
      persistSettings({ ...settings, ...patchSettings });
    },
    [settings, persistSettings],
  );

  const resetDemo = useCallback(() => {
    const seedItems = buildDemoItems();
    const seedSettings = buildDemoSettings();
    persistItems(seedItems);
    persistSettings(seedSettings);
  }, [persistItems, persistSettings]);

  const defaultDueDate = useMemo(() => {
    const cfg = settings.projectConfigs[settings.activeProject];
    return addDays(cfg?.defaultDueDays ?? 7);
  }, [settings]);

  const pendingSyncCount = useMemo(() => items.filter((i) => i.sync === "pending" || i.sync === "offline").length, [items]);

  return useMemo(
    () => ({
      items,
      settings,
      hydrated,
      online,
      pendingSyncCount,
      defaultDueDate,
      getItem: (id: string) => items.find((i) => i.id === id),
      create,
      issue,
      markInProgress,
      markReady,
      startInspection,
      reject,
      closeWithEvidence,
      completeIncomplete,
      reopen,
      addRectification,
      addComment,
      setActiveProject,
      addProject,
      updateProjectConfig,
      addSubcontractor,
      updateProfile,
      updateCompany,
      resetDemo,
    }),
    [
      items,
      settings,
      hydrated,
      online,
      pendingSyncCount,
      defaultDueDate,
      create,
      issue,
      markInProgress,
      markReady,
      startInspection,
      reject,
      closeWithEvidence,
      completeIncomplete,
      reopen,
      addRectification,
      addComment,
      setActiveProject,
      addProject,
      updateProjectConfig,
      addSubcontractor,
      updateProfile,
      updateCompany,
      resetDemo,
    ],
  );
});

export function useActiveProjectConfig(): ProjectConfig {
  const { settings } = useAppStore();
  return (
    settings.projectConfigs[settings.activeProject] ?? {
      name: settings.activeProject,
      buildings: [],
      levels: [],
      units: [],
      rooms: [],
      defaultDueDays: 7,
    }
  );
}
