// This file follows the Supabase generated types shape.
// Regenerate after every migration:
//   supabase gen types typescript --local > supabase/types/database.types.ts

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          display_name: string;
          role: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          display_name?: string;
          role?: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          display_name?: string;
          role?: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
          updated_at?: string;
        };
        Relationships: [];
      };
      projects: {
        Row: {
          id: string;
          name: string;
          address: string | null;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          address?: string | null;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          name?: string;
          address?: string | null;
          created_by?: string | null;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "projects_created_by_fkey";
            columns: ["created_by"];
            referencedRelation: "profiles";
            referencedColumns: ["id"];
          }
        ];
      };
      project_members: {
        Row: {
          id: string;
          project_id: string;
          user_id: string;
          role: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
          created_at: string;
        };
        Insert: {
          id?: string;
          project_id: string;
          user_id: string;
          role: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
          created_at?: string;
        };
        Update: {
          role?: "owner" | "admin" | "project_manager" | "site_manager" | "subcontractor" | "viewer";
        };
        Relationships: [];
      };
      subcontractors: {
        Row: {
          id: string;
          project_id: string | null;
          name: string;
          trade: string | null;
          email: string | null;
          phone: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          project_id?: string | null;
          name: string;
          trade?: string | null;
          email?: string | null;
          phone?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          project_id?: string | null;
          name?: string;
          trade?: string | null;
          email?: string | null;
          phone?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      items: {
        Row: {
          id: string;
          code: string;
          type: "defect" | "incomplete" | "client";
          status: "open" | "issued" | "in_progress" | "ready_for_review" | "under_inspection" | "rejected" | "closed" | "complete";
          project_id: string | null;
          project: string;
          building: string | null;
          level: string | null;
          unit: string | null;
          room: string | null;
          trade: string | null;
          subcontractor_id: string | null;
          subcontractor: string | null;
          priority: "high" | "urgent" | null;
          due_date: string | null;
          description: string | null;
          raised_by: string | null;
          created_by: string | null;
          created_by_label: string | null;
          rejection_reason: string | null;
          issued_at: string | null;
          started_at: string | null;
          ready_at: string | null;
          inspected_at: string | null;
          closed_at: string | null;
          created_at: string;
          updated_at: string;
          payload: Json;
        };
        Insert: {
          id?: string;
          code: string;
          type: "defect" | "incomplete" | "client";
          status?: "open" | "issued" | "in_progress" | "ready_for_review" | "under_inspection" | "rejected" | "closed" | "complete";
          project_id?: string | null;
          project: string;
          building?: string | null;
          level?: string | null;
          unit?: string | null;
          room?: string | null;
          trade?: string | null;
          subcontractor_id?: string | null;
          subcontractor?: string | null;
          priority?: "high" | "urgent" | null;
          due_date?: string | null;
          description?: string | null;
          raised_by?: string | null;
          created_by?: string | null;
          created_by_label?: string | null;
          rejection_reason?: string | null;
          issued_at?: string | null;
          started_at?: string | null;
          ready_at?: string | null;
          inspected_at?: string | null;
          closed_at?: string | null;
          created_at?: string;
          updated_at?: string;
          payload?: Json;
        };
        Update: {
          status?: "open" | "issued" | "in_progress" | "ready_for_review" | "under_inspection" | "rejected" | "closed" | "complete";
          project_id?: string | null;
          project?: string;
          building?: string | null;
          level?: string | null;
          unit?: string | null;
          room?: string | null;
          trade?: string | null;
          subcontractor_id?: string | null;
          subcontractor?: string | null;
          priority?: "high" | "urgent" | null;
          due_date?: string | null;
          description?: string | null;
          raised_by?: string | null;
          created_by?: string | null;
          created_by_label?: string | null;
          rejection_reason?: string | null;
          issued_at?: string | null;
          started_at?: string | null;
          ready_at?: string | null;
          inspected_at?: string | null;
          closed_at?: string | null;
          updated_at?: string;
          payload?: Json;
        };
        Relationships: [];
      };
      evidence: {
        Row: {
          id: string;
          item_id: string;
          evidence_type: "original" | "rectification" | "closeout";
          storage_path: string | null;
          photo: string | null;
          comment: string | null;
          note: string | null;
          role: string | null;
          confirmation: string | null;
          uploaded_by: string | null;
          uploaded_by_label: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          item_id: string;
          evidence_type: "original" | "rectification" | "closeout";
          storage_path?: string | null;
          photo?: string | null;
          comment?: string | null;
          note?: string | null;
          role?: string | null;
          confirmation?: string | null;
          uploaded_by?: string | null;
          uploaded_by_label?: string | null;
          created_at?: string;
        };
        Update: {
          storage_path?: string | null;
          photo?: string | null;
          comment?: string | null;
          note?: string | null;
          role?: string | null;
          confirmation?: string | null;
          uploaded_by?: string | null;
          uploaded_by_label?: string | null;
        };
        Relationships: [];
      };
      comments: {
        Row: {
          id: string;
          item_id: string;
          text: string;
          created_by: string | null;
          created_by_label: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          item_id: string;
          text: string;
          created_by?: string | null;
          created_by_label?: string | null;
          created_at?: string;
        };
        Update: {
          text?: string;
          created_by?: string | null;
          created_by_label?: string | null;
        };
        Relationships: [];
      };
      audit_events: {
        Row: {
          id: string;
          item_id: string | null;
          event_type: string;
          message: string;
          created_by: string | null;
          created_by_label: string | null;
          created_at: string;
          idempotency_key: string | null;
        };
        Insert: {
          id?: string;
          item_id?: string | null;
          event_type: string;
          message: string;
          created_by?: string | null;
          created_by_label?: string | null;
          created_at?: string;
          idempotency_key?: string | null;
        };
        Update: never;
        Relationships: [];
      };
      app_settings: {
        Row: {
          id: string;
          project_id: string | null;
          payload: Json;
          updated_at: string;
        };
        Insert: {
          id?: string;
          project_id?: string | null;
          payload: Json;
          updated_at?: string;
        };
        Update: {
          project_id?: string | null;
          payload?: Json;
          updated_at?: string;
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};
