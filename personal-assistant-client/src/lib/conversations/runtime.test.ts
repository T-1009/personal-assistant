import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversation: vi.fn(),
  listConversations: vi.fn(),
  loadConversationHistory: vi.fn(),
  patchConversation: vi.fn(),
}));

vi.mock("./api", () => api);

import { conversationThreadListAdapter } from "./runtime";

const active = {
  id: "11111111-1111-4111-8111-111111111111",
  title: "Active",
  status: "active" as const,
  createdAt: new Date("2026-07-15T08:00:00Z"),
  updatedAt: new Date("2026-07-15T09:00:00Z"),
  archivedAt: null,
};

const archived = {
  ...active,
  id: "22222222-2222-4222-8222-222222222222",
  title: "Archived",
  status: "archived" as const,
  archivedAt: new Date("2026-07-15T09:00:00Z"),
};

describe("Conversation remote thread adapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("merges active and archived pages and preserves both cursors", async () => {
    api.listConversations
      .mockResolvedValueOnce({ items: [active], nextCursor: "active-next" })
      .mockResolvedValueOnce({ items: [archived], nextCursor: undefined })
      .mockResolvedValueOnce({ items: [], nextCursor: undefined });

    const first = await conversationThreadListAdapter.list();
    const second = await conversationThreadListAdapter.list({
      after: first.nextCursor,
    });

    expect(first.threads).toEqual([
      expect.objectContaining({
        status: "regular",
        remoteId: active.id,
        externalId: active.id,
      }),
      expect.objectContaining({
        status: "archived",
        remoteId: archived.id,
        externalId: archived.id,
      }),
    ]);
    expect(first.nextCursor).toEqual(expect.any(String));
    expect(second.nextCursor).toBeUndefined();
    expect(api.listConversations).toHaveBeenNthCalledWith(
      3,
      "active",
      "active-next",
    );
  });

  it("maps initialize and Conversation mutations to the API", async () => {
    api.createConversation.mockResolvedValue(active);
    api.getConversation.mockResolvedValue(archived);

    await expect(
      conversationThreadListAdapter.initialize("local-thread"),
    ).resolves.toEqual({ remoteId: active.id, externalId: active.id });
    await conversationThreadListAdapter.rename(active.id, "Renamed");
    await conversationThreadListAdapter.archive(active.id);
    await conversationThreadListAdapter.unarchive(active.id);
    await conversationThreadListAdapter.delete(active.id);
    await expect(conversationThreadListAdapter.fetch(archived.id)).resolves.toEqual(
      expect.objectContaining({
        status: "archived",
        remoteId: archived.id,
        externalId: archived.id,
      }),
    );

    expect(api.patchConversation).toHaveBeenCalledWith(active.id, {
      title: "Renamed",
    });
    expect(api.patchConversation).toHaveBeenCalledWith(active.id, {
      status: "archived",
    });
    expect(api.patchConversation).toHaveBeenCalledWith(active.id, {
      status: "active",
    });
    expect(api.deleteConversation).toHaveBeenCalledWith(active.id);
  });
});
