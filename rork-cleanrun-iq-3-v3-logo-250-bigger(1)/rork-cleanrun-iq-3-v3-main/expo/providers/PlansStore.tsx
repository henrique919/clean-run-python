import createContextHook from "@nkzw/create-context-hook";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { buildDemoPlans } from "@/lib/demoSeed";
import { makeId } from "@/lib/format";
import { Plan, PlanPin } from "@/types/models";

const KEY = "cleanrun-iq:plans:v1";

export const [PlansProvider, usePlans] = createContextHook(() => {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [hydrated, setHydrated] = useState<boolean>(false);

  const hydration = useQuery({
    queryKey: ["cleanrun-plans-hydrate"],
    queryFn: async () => {
      const raw = await AsyncStorage.getItem(KEY);
      let next: Plan[];
      try {
        next = raw ? (JSON.parse(raw) as Plan[]) : buildDemoPlans();
      } catch {
        next = buildDemoPlans();
      }
      if (!raw) await AsyncStorage.setItem(KEY, JSON.stringify(next));
      return next;
    },
    staleTime: Infinity,
  });

  useEffect(() => {
    if (hydration.data && !hydrated) {
      setPlans(hydration.data);
      setHydrated(true);
    }
  }, [hydration.data, hydrated]);

  const persist = useCallback((next: Plan[]) => {
    setPlans(next);
    AsyncStorage.setItem(KEY, JSON.stringify(next)).catch((e) => console.warn("[CleanRun] plan persist failed", e));
  }, []);

  const addPlan = useCallback(
    (input: Omit<Plan, "id" | "pins" | "createdAt">): Plan => {
      const plan: Plan = { ...input, id: makeId(), pins: [], createdAt: new Date().toISOString() };
      persist([plan, ...plans]);
      return plan;
    },
    [plans, persist],
  );

  const removePlan = useCallback((id: string) => persist(plans.filter((p) => p.id !== id)), [plans, persist]);

  const addPin = useCallback(
    (planId: string, pin: Omit<PlanPin, "id">): PlanPin => {
      const created: PlanPin = { id: makeId(), ...pin };
      persist(plans.map((p) => (p.id === planId ? { ...p, pins: [...p.pins, created] } : p)));
      return created;
    },
    [plans, persist],
  );

  const updatePin = useCallback(
    (planId: string, pinId: string, patch: Partial<PlanPin>) => {
      persist(plans.map((p) => (p.id === planId ? { ...p, pins: p.pins.map((pn) => (pn.id === pinId ? { ...pn, ...patch } : pn)) } : p)));
    },
    [plans, persist],
  );

  const removePin = useCallback(
    (planId: string, pinId: string) => {
      persist(plans.map((p) => (p.id === planId ? { ...p, pins: p.pins.filter((pn) => pn.id !== pinId) } : p)));
    },
    [plans, persist],
  );

  return useMemo(
    () => ({ plans, hydrated, addPlan, removePlan, addPin, updatePin, removePin }),
    [plans, hydrated, addPlan, removePlan, addPin, updatePin, removePin],
  );
});
