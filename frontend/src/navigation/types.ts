import { UploadedNote } from '../api/notes';

export type RootTabParamList = {
  Home: undefined;
  Record: undefined;
  Processing: undefined;
  Result: { note?: UploadedNote; recordingUri?: string } | undefined;
  Settings: undefined;
};
